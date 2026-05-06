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
KSeF v2 uses a multi-step challenge/redeem flow to issue an AccessToken.  This
module accepts an already-obtained AccessToken (passed as KSEF_SESSION_TOKEN or
via the session_token tool parameter) and sends it as a Bearer token.  The auth
flow itself must be completed by the caller.

Full auth documentation:
  https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md

Invoice format note
-------------------
KSeF API v2 online sessions accept only FA(3) schema (systemCode "FA (3)",
schemaVersion "1-0E").  FA(2) XML is not accepted for new submissions.
[NEED] Implement FA(3) generator (generate_fa3_invoice tool) before attempting
live submissions.  See roadmap-2026.md.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp_einvoicing_core import (
    AuthMode,
    BaseEInvoicingClient,
    BaseLifecycleManager,
    PlatformError,
)
from mcp_einvoicing_core.logging_utils import get_logger

from ._encryption import InvoiceEnvelope, load_mf_public_key
from .config import KSeFSettings

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
        response = await self._request(
            "POST", "/invoices/query/metadata", json=payload
        )
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

    async def submit_document(self, xml: str, metadata: dict[str, Any]) -> str:
        """Submit a FA(3) XML invoice to KSeF v2.

        Internally: fetches MF public key, opens session, sends encrypted
        invoice, closes session.

        metadata keys
        -------------
        session_token   : str, optional  — overrides KSEF_SESSION_TOKEN
        form_code       : dict, optional — overrides the default FA(3) formCode

        Returns:
            "{sessionRef}:{invoiceRef}" — pass this to get_document_status.
        """
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

        form_code: dict[str, str] | None = metadata.get("form_code")

        logger.info(
            "Submitting invoice to KSeF v2 (%s)", self._settings.environment
        )

        # Step 1: fetch the MF public key for symmetric key encryption.
        certs = await self._client.get_public_key_certificates()
        cert_b64 = _pick_encryption_cert(certs)
        mf_public_key = load_mf_public_key(cert_b64)

        # Step 2: build the per-session envelope (AES key + IV + RSA-wrapped key).
        envelope = InvoiceEnvelope(mf_public_key)

        # Step 3: open the interactive session.
        session_ref = await self._client.open_online_session(
            encrypted_symmetric_key=envelope.encrypted_symmetric_key,
            initialization_vector=envelope.initialization_vector,
            form_code=form_code,
        )
        logger.info("KSeF session opened: %s", session_ref)

        # Step 4: encrypt and send the invoice.
        send_payload = envelope.build_send_payload(xml)
        invoice_ref = await self._client.send_invoice_to_session(
            session_ref, send_payload
        )
        logger.info("Invoice sent to session %s: invoiceRef=%s", session_ref, invoice_ref)

        # Step 5: close the session (non-fatal if this fails — invoice is already sent).
        try:
            await self._client.close_online_session(session_ref)
            logger.info("KSeF session closed: %s", session_ref)
        except Exception as exc:
            logger.warning(
                "Session close failed (non-fatal, invoice was accepted): %s", exc
            )

        # Return compound reference understood by get_document_status.
        return f"{session_ref}:{invoice_ref}"

    async def get_document_status(self, document_id: str) -> dict[str, Any]:
        """Get the status of a submitted invoice.

        Args:
            document_id: Either the compound "{sessionRef}:{invoiceRef}" string
                         returned by submit_document, or just a sessionRef to get
                         the overall session status.
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
        date_type    : str  "Issue" | "Invoicing" | "PermanentStorage"
                            (default "Invoicing")
        """
        date_from = _to_iso_datetime(
            filters.get("date_from", str(date.today())), end=False
        )
        date_to = _to_iso_datetime(
            filters.get("date_to", str(date.today())), end=True
        )
        subject_type = filters.get("subject_type", "Subject1")
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
    date has not yet passed.

    Raises:
        PlatformError: If no suitable certificate is found.
    """
    for cert in certs:
        usages: list[str] = cert.get("usage", [])
        if "SymmetricKeyEncryption" in usages:
            certificate = cert.get("certificate", "")
            if certificate:
                return certificate
    raise PlatformError(
        status_code=502,
        message=(
            "No SymmetricKeyEncryption certificate found in KSeF public-key response. "
            f"Returned certificates: {[c.get('usage') for c in certs]}"
        ),
    )


def _to_iso_datetime(value: str, *, end: bool) -> str:
    """Normalise a YYYY-MM-DD or ISO datetime string to a full ISO-8601 datetime.

    If *value* is already a full ISO string (contains 'T'), return it unchanged.
    Otherwise append T00:00:00+00:00 (start of day) or T23:59:59+00:00 (end).
    """
    if "T" in value:
        return value
    suffix = "T23:59:59+00:00" if end else "T00:00:00+00:00"
    return f"{value}{suffix}"
