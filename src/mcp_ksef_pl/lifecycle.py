"""KSeF API v2 lifecycle manager — session, submission, status, and search.

KSeF API v2 submission flow
---------------------------
1. Fetch the Ministry of Finance RSA public key:
   GET /security/public-key-certificates
   Filter to the certificate with usage "SymmetricKeyEncryption".

2. Build an InvoiceEnvelope (generates AES-256 key + IV, wraps key with MF RSA
   public key via OAEP-SHA256).

3. Open an interactive session declaring the invoice schema and encryption info:
   POST /sessions/online
   Body: { formCode: {systemCode, schemaVersion, value}, encryption: {encryptedSymmetricKey, IV} }
   Response: { referenceNumber: <sessionRef> }

4. Encrypt the invoice XML with the envelope and send it:
   POST /sessions/online/{sessionRef}/invoices
   Body: { invoiceHash, invoiceSize, encryptedInvoiceHash,
           encryptedInvoiceSize, encryptedInvoiceContent }
   Response: { referenceNumber: <invoiceRef> }

5. Close the session (triggers UPO generation):
   POST /sessions/online/{sessionRef}/close

6. Check processing status:
   GET /sessions/{sessionRef}/invoices/{invoiceRef}

Authentication note
-------------------
KSeF v2 uses a multi-step challenge/redeem flow to issue an AccessToken:
  1. POST /auth/challenge (obtain challenge + timestamp)
  2. Build <InitSessionTokenRequest> XML, sign with qualified e-signature (PKCS#12)
  3. POST /auth/xades-signature (submit signed XML, receive an authOperation reference)
  4. POST /auth/token/redeem (exchange the authenticated operation for an AccessToken)
  Token validity: approximately 2 hours from issuance.

This module accepts an already-obtained AccessToken (passed as KSEF_SESSION_TOKEN
or via the session_token tool parameter) and sends it as a Bearer token.

Full auth documentation:
  https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md

Invoice format note
-------------------
KSeF API v2 online sessions accept only FA(3) schema (systemCode "FA (3)",
schemaVersion "1-0E").  FA(2) XML is not accepted for new submissions.
FA(3) generator is implemented as generate_fa3_invoice in server.py.
"""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from typing import Any

from mcp_einvoicing_core import (
    AuthMode,
    BaseEInvoicingClient,
    BaseLifecycleManager,
    PlatformError,
    SubmitResult,
)
from mcp_einvoicing_core.logging_utils import get_logger

from ._encryption import InvoiceEnvelope, load_mf_public_key
from .config import KSeFSettings
from .models import SubjectType
from .security import MFKeyPinningError, verify_mf_spki_pin

logger = get_logger(__name__)

# formCode declared when opening a KSeF v2 online session.
# KSeF API v2 supports FA(3) for new submissions; FA(2) is not accepted.
_FORM_CODE_FA3 = {
    "systemCode": "FA (3)",
    "schemaVersion": "1-0E",
    "value": "FA",
}


class KSeFClient(BaseEInvoicingClient):
    """Thin async HTTP wrapper around the KSeF REST API v2."""

    def __init__(self, settings: KSeFSettings) -> None:
        super().__init__(
            base_url=settings.base_url,
            auth_mode=AuthMode.BEARER_TOKEN,
            oauth_config=None,
            static_bearer_token=settings.session_token or None,
            http_timeout=float(settings.timeout),
        )

    def update_access_token(self, token: str) -> None:
        self._static_token = token

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:  # type: ignore[override]
        """Override _request to parse KSeF-structured error bodies (PL-3.2)."""
        try:
            return await super()._request(method, path, **kwargs)
        except PlatformError as exc:
            # Re-raise with KSeF-specific error body parsed when available.
            if hasattr(exc, "response_body") and exc.response_body:
                _raise_ksef_error(exc.status_code, exc.response_body)
            raise

    # ------------------------------------------------------------------
    # Public-key certificates
    # ------------------------------------------------------------------

    async def get_public_key_certificates(self) -> list[dict[str, Any]]:
        """GET /security/public-key-certificates — returns array of cert objects."""
        response = await self._request("GET", "/security/public-key-certificates")
        return response.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Online session lifecycle (v2)
    # ------------------------------------------------------------------

    async def open_online_session(
        self,
        encrypted_symmetric_key: str,
        initialization_vector: str,
        form_code: dict[str, str] | None = None,
    ) -> str:
        """POST /sessions/online — open an interactive session.

        Returns:
            Session referenceNumber.
        """
        payload: dict[str, Any] = {
            "formCode": form_code or _FORM_CODE_FA3,
            "encryption": {
                "encryptedSymmetricKey": encrypted_symmetric_key,
                "initializationVector": initialization_vector,
            },
        }
        response = await self._request("POST", "/sessions/online", json=payload)
        data: dict[str, Any] = response.json()
        ref = data.get("referenceNumber", "")
        if not ref:
            raise PlatformError(
                status_code=500,
                message=f"KSeF did not return a session referenceNumber. Response: {data}",
            )
        return str(ref)

    async def send_invoice_to_session(
        self,
        session_reference: str,
        send_payload: dict[str, Any],
    ) -> str:
        """POST /sessions/online/{sessionRef}/invoices — send one encrypted invoice.

        Returns:
            Invoice referenceNumber.
        """
        response = await self._request(
            "POST",
            f"/sessions/online/{session_reference}/invoices",
            json=send_payload,
        )
        data: dict[str, Any] = response.json()
        ref = data.get("referenceNumber", "")
        if not ref:
            raise PlatformError(
                status_code=500,
                message=f"KSeF did not return an invoice referenceNumber. Response: {data}",
            )
        return str(ref)

    async def close_online_session(self, session_reference: str) -> None:
        """POST /sessions/online/{sessionRef}/close — close session, trigger UPO."""
        await self._request("POST", f"/sessions/online/{session_reference}/close")

    # ------------------------------------------------------------------
    # Status and search (v2)
    # ------------------------------------------------------------------

    async def get_invoice_status(
        self,
        session_reference: str,
        invoice_reference: str,
    ) -> dict[str, Any]:
        """GET /sessions/{sessionRef}/invoices/{invoiceRef} — invoice status."""
        response = await self._request(
            "GET",
            f"/sessions/{session_reference}/invoices/{invoice_reference}",
        )
        return response.json()  # type: ignore[no-any-return]

    async def get_session_status(self, session_reference: str) -> dict[str, Any]:
        """GET /sessions/{sessionRef} — overall session status."""
        response = await self._request("GET", f"/sessions/{session_reference}")
        return response.json()  # type: ignore[no-any-return]

    async def query_invoices(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /invoices/query/metadata — search invoice metadata."""
        response = await self._request("POST", "/invoices/query/metadata", json=payload)
        return response.json()  # type: ignore[no-any-return]

    async def healthcheck(self) -> dict[str, Any]:
        """GET /limits/context — lightweight liveness check."""
        response = await self._request("GET", "/limits/context")
        return response.json()  # type: ignore[no-any-return]


class KSeFLifecycleManager(BaseLifecycleManager):
    """KSeF v2 invoice lifecycle: submit, status, and search.

    Submission is a three-step operation under the hood (open session, send
    encrypted invoice, close session), but it is exposed as a single
    submit_document call matching the BaseLifecycleManager contract.

    The caller must supply an AccessToken (KSEF_SESSION_TOKEN or the
    session_token metadata key).  Obtaining the token is outside this module.
    """

    def __init__(self, settings: KSeFSettings | None = None) -> None:
        self._settings = settings or KSeFSettings()
        self._client = KSeFClient(self._settings)

    # ------------------------------------------------------------------
    # BaseLifecycleManager implementation
    # ------------------------------------------------------------------

    async def submit_document(  # type: ignore[override]
        self,
        document: bytes | str,
        metadata: dict[str, Any],
    ) -> SubmitResult:
        """Submit a FA(3) XML invoice to KSeF v2.

        Internally: fetches MF public key, opens session, sends encrypted
        invoice, closes session.

        metadata keys
        -------------
        session_token          : str, optional  — overrides KSEF_SESSION_TOKEN
        form_code              : dict, optional — overrides the default FA(3) formCode
        session_token_expires_at: str, optional — ISO-8601 datetime; a warning is logged
                                  if the token expires within 60 seconds (PL-3.4)

        Returns:
            SubmitResult with session_ref and invoice_ref populated.
            Pass result.compound_id to get_document_status.
        """
        xml = document if isinstance(document, str) else document.decode("utf-8")
        if token := metadata.get("session_token"):
            self._client.update_access_token(token)

        if not self._client._static_token:
            raise PlatformError(
                status_code=401,
                message=(
                    "No KSeF AccessToken provided. Obtain one via the KSeF v2 auth flow "
                    "(challenge → authenticate → redeem) and pass it as KSEF_SESSION_TOKEN "
                    "or metadata['session_token']."
                ),
            )

        # PL-3.4: Pre-flight token expiry check.
        expires_at_str: str = metadata.get("session_token_expires_at", "")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                seconds_left = (expires_at - datetime.now(UTC)).total_seconds()
                if seconds_left <= 0:
                    raise PlatformError(
                        status_code=401,
                        message=(
                            f"KSeF AccessToken expired at {expires_at_str}. "
                            "Obtain a new token before submitting."
                        ),
                    )
                if seconds_left < 60:
                    logger.warning(
                        "KSeF AccessToken expires in %.0f seconds — refresh before submission",
                        seconds_left,
                    )
            except PlatformError:
                raise
            except ValueError:
                logger.warning(
                    "Could not parse session_token_expires_at=%r — skipping expiry check",
                    expires_at_str,
                )

        form_code: dict[str, str] | None = metadata.get("form_code")

        logger.info("Submitting invoice to KSeF v2 (%s)", self._settings.environment)

        # Step 1: fetch the MF public key for symmetric key encryption.
        certs = await self._client.get_public_key_certificates()
        cert_b64 = _pick_encryption_cert(certs)

        # PL-3.6: verify the cert's SPKI fingerprint against the pinned
        # allowlist before trusting it. No-op unless verify_mf_key_pinning is
        # enabled AND a pin exists for the active environment.
        try:
            verify_mf_spki_pin(
                base64.b64decode(cert_b64),
                self._settings.environment.value,
                enforce=self._settings.verify_mf_key_pinning,
            )
        except MFKeyPinningError as exc:
            raise PlatformError(status_code=502, message=str(exc)) from exc

        mf_public_key = load_mf_public_key(cert_b64)

        # Step 2: build the per-session envelope (AES key + IV + RSA-wrapped key).
        envelope = InvoiceEnvelope(mf_public_key)

        try:
            # Step 3: open the interactive session.
            session_ref = await self._client.open_online_session(
                encrypted_symmetric_key=envelope.encrypted_symmetric_key,
                initialization_vector=envelope.initialization_vector,
                form_code=form_code,
            )
            logger.info("KSeF session opened: %s", session_ref)

            # Step 4: encrypt and send the invoice.
            send_payload = envelope.build_send_payload(xml)
            invoice_ref = await self._client.send_invoice_to_session(session_ref, send_payload)
            logger.info("Invoice sent to session %s: invoiceRef=%s", session_ref, invoice_ref)

            # Step 5: close the session (non-fatal if this fails — invoice is already sent).
            try:
                await self._client.close_online_session(session_ref)
                logger.info("KSeF session closed: %s", session_ref)
            except Exception as exc:
                logger.warning("Session close failed (non-fatal, invoice was accepted): %s", exc)
        finally:
            # Drop AES key references regardless of outcome to minimise the
            # window during which key material is reachable in process memory.
            envelope.cleanup()

        return SubmitResult(
            invoice_ref=invoice_ref,
            session_ref=session_ref,
            status="submitted",
        )

    async def get_document_status(self, document_id: str) -> dict[str, Any]:
        """Get the status of a submitted invoice.

        Args:
            document_id: Pass ``result.compound_id`` from a SubmitResult, or any
                         ``"{sessionRef}:{invoiceRef}"`` compound string.  Pass a
                         bare sessionRef (no colon) to get the overall session status.
        """
        if ":" in document_id:
            session_ref, invoice_ref = document_id.split(":", 1)
            return await self._client.get_invoice_status(session_ref, invoice_ref)
        return await self._client.get_session_status(document_id)

    async def search_documents(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query KSeF invoice metadata.

        filters keys
        ------------
        date_from    : str  ISO-8601 datetime or YYYY-MM-DD (defaults to today 00:00Z)
        date_to      : str  ISO-8601 datetime or YYYY-MM-DD (defaults to today 23:59Z)
        subject_type : str  "Subject1" (seller) | "Subject2" (buyer) | "Subject3"
                            | "SubjectAuthorized"  (default "Subject1")
                            Case-insensitive; normalized to the KSeF v2 PascalCase
                            enum. Raises PlatformError for unrecognised values.
        date_type    : str  "Issue" | "Invoicing" | "PermanentStorage"
                            (default "Invoicing")
        """
        date_from = _to_iso_datetime(filters.get("date_from", str(date.today())), end=False)
        date_to = _to_iso_datetime(filters.get("date_to", str(date.today())), end=True)
        subject_type = _normalize_subject_type(filters.get("subject_type", "Subject1"))
        date_type = filters.get("date_type", "Invoicing")

        payload: dict[str, Any] = {
            "subjectType": subject_type,
            "dateRange": {
                "dateType": date_type,
                "from": date_from,
                "to": date_to,
            },
        }
        result = await self._client.query_invoices(payload)
        return result.get("invoices", [])  # type: ignore[return-value]

    async def healthcheck(self) -> dict[str, Any]:
        try:
            data = await self._client.healthcheck()
            return {"status": "ok", "ksef_response": data}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _pick_encryption_cert(certs: list[dict[str, Any]]) -> str:
    """Return the Base64 DER certificate suitable for SymmetricKeyEncryption.

    KSeF v2 returns multiple certificates with different usages.  Select the
    one whose usage array contains "SymmetricKeyEncryption" and whose validTo
    date has not yet passed (PL-3.1).

    Raises:
        PlatformError: If no non-expired suitable certificate is found.
    """
    now = datetime.now(UTC)
    for cert in certs:
        usages: list[str] = cert.get("usage", [])
        if "SymmetricKeyEncryption" not in usages:
            continue
        certificate = cert.get("certificate", "")
        if not certificate:
            continue
        valid_to_str = cert.get("validTo", "")
        if valid_to_str:
            try:
                valid_to = datetime.fromisoformat(valid_to_str.replace("Z", "+00:00"))
                if valid_to <= now:
                    logger.warning(
                        "Skipping expired SymmetricKeyEncryption cert (validTo=%s)", valid_to_str
                    )
                    continue
            except ValueError:
                # Cannot parse validTo — accept and let KSeF reject if invalid
                pass
        return certificate
    raise PlatformError(
        status_code=502,
        message=(
            "No valid (non-expired) SymmetricKeyEncryption certificate found in KSeF "
            "public-key response. "
            f"Returned certificates: {[c.get('usage') for c in certs]}"
        ),
    )


def _raise_ksef_error(status_code: int, body: bytes | str) -> None:
    """Parse a KSeF API error body and raise a typed PlatformError (PL-3.2).

    KSeF v2 returns structured JSON for 400/401/404/409 responses:
      { "exceptionCode": "AUTH_001", "message": "..." }

    If the body is not JSON or lacks the expected fields, falls back to the
    raw text to avoid hiding the original error.

    Raises:
        PlatformError: Always — this function never returns normally.
    """
    import json

    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    try:
        data: dict[str, Any] = json.loads(text)
        exception_code: str = data.get("exceptionCode", "")
        message: str = data.get("message", text)
        detail = f"[{exception_code}] {message}" if exception_code else message
    except (json.JSONDecodeError, AttributeError):
        detail = text or f"HTTP {status_code}"

    raise PlatformError(status_code=status_code, message=detail)


_SUBJECT_TYPE_LOOKUP: dict[str, SubjectType] = {
    member.value.lower(): member for member in SubjectType
}


def _normalize_subject_type(value: str) -> str:
    """Normalize a case-insensitive subjectType input to the KSeF v2 PascalCase enum.

    Raises:
        PlatformError: If *value* does not match any SubjectType member.
    """
    normalized = _SUBJECT_TYPE_LOOKUP.get(value.strip().lower())
    if normalized is None:
        raise PlatformError(
            status_code=400,
            message=(
                f"Unrecognised subject_type {value!r}. Expected one of: "
                f"{', '.join(m.value for m in SubjectType)}."
            ),
        )
    return normalized.value


def _to_iso_datetime(value: str, *, end: bool) -> str:
    """Normalise a YYYY-MM-DD or ISO datetime string to a full ISO-8601 datetime.

    If *value* is already a full ISO string (contains 'T'), return it unchanged.
    Otherwise append T00:00:00+00:00 (start of day) or T23:59:59+00:00 (end).
    """
    if "T" in value:
        return value
    suffix = "T23:59:59+00:00" if end else "T00:00:00+00:00"
    return f"{value}{suffix}"
