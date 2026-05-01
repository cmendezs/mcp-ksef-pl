"""KSeF platform lifecycle manager — session, submission, status, and search.

Authentication note
-------------------
KSeF requires a signed XML InitToken challenge before a session token is issued.
The signing step (qualified e-signature or MF-portal token) must be performed by
the caller.  This manager accepts an already-obtained *session_token* and handles
all subsequent API interactions.

KSeF API reference: https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/
"""

from __future__ import annotations

import base64
from datetime import date
from typing import Any

from mcp_einvoicing_core import (
    AuthMode,
    BaseEInvoicingClient,
    BaseLifecycleManager,
    PlatformError,
)
from mcp_einvoicing_core.logging_utils import get_logger

from .config import KSeFSettings

logger = get_logger(__name__)


class KSeFClient(BaseEInvoicingClient):
    """Thin HTTP wrapper around the KSeF REST API using a bearer session token."""

    def __init__(self, settings: KSeFSettings) -> None:
        super().__init__(
            base_url=settings.base_url,
            auth_mode=AuthMode.BEARER_TOKEN,
            oauth_config=None,
            static_bearer_token=settings.session_token or None,
            http_timeout=float(settings.timeout),
        )

    def update_session_token(self, token: str) -> None:
        # _static_token is the private attr used by BaseEInvoicingClient for BEARER_TOKEN mode
        self._static_token = token

    # ------------------------------------------------------------------
    # Raw KSeF API helpers
    # ------------------------------------------------------------------

    async def send_invoice(self, xml_content: str) -> dict[str, Any]:
        """PUT /online/Invoice/Send — encode XML as Base64 and submit."""
        encoded = base64.b64encode(xml_content.encode()).decode()
        payload = {
            "invoiceHash": {
                "fileSize": len(xml_content.encode()),
                "hashSHA": {"algorithm": "SHA-256", "encoding": "Base64", "value": ""},
            },
            "invoicePayload": {
                "type": "plain",
                "invoiceBody": encoded,
            },
        }
        response = await self._request("PUT", "/online/Invoice/Send", json=payload)
        return response.json()  # type: ignore[no-any-return]

    async def get_invoice_status(self, reference_number: str) -> dict[str, Any]:
        """GET /online/Invoice/Status/{referenceNumber}"""
        response = await self._request("GET", f"/online/Invoice/Status/{reference_number}")
        return response.json()  # type: ignore[no-any-return]

    async def query_invoices(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /online/Query/Invoice/Sync"""
        response = await self._request("POST", "/online/Query/Invoice/Sync", json=payload)
        return response.json()  # type: ignore[no-any-return]

    async def terminate_session(self) -> None:
        """GET /online/Session/Terminate"""
        await self._request("GET", "/online/Session/Terminate")


class KSeFLifecycleManager(BaseLifecycleManager):
    """Manages the full KSeF invoice lifecycle: submit → status → search."""

    def __init__(self, settings: KSeFSettings | None = None) -> None:
        self._settings = settings or KSeFSettings()
        self._client = KSeFClient(self._settings)

    # ------------------------------------------------------------------
    # BaseLifecycleManager implementation
    # ------------------------------------------------------------------

    async def submit_document(self, xml: str, metadata: dict[str, Any]) -> str:
        """Submit *xml* to KSeF and return the elementReferenceNumber.

        metadata keys
        -------------
        session_token : str, optional  — override settings session token
        terminate_after : bool         — call Session/Terminate after send (default True)
        """
        if token := metadata.get("session_token"):
            self._client.update_session_token(token)

        if not self._client._static_token:
            raise PlatformError(
                status_code=401,
                message="No KSeF session token provided. Obtain one via the KSeF auth flow and pass it as KSEF_SESSION_TOKEN or in metadata['session_token'].",
            )

        logger.info("Submitting invoice to KSeF (%s)", self._settings.environment)
        result = await self._client.send_invoice(xml)

        reference = (
            result.get("elementReferenceNumber")
            or result.get("referenceNumber")
            or result.get("invoiceNumber")
            or ""
        )
        if not reference:
            raise PlatformError(
                status_code=500,
                message=f"KSeF did not return a reference number. Response: {result}",
            )

        if metadata.get("terminate_after", True):
            try:
                await self._client.terminate_session()
            except Exception as exc:
                logger.warning("Session termination failed (non-fatal): %s", exc)

        return str(reference)

    async def get_document_status(self, document_id: str) -> dict[str, Any]:
        return await self._client.get_invoice_status(document_id)

    async def search_documents(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query KSeF invoices.

        filters keys
        ------------
        date_from   : str  YYYY-MM-DD
        date_to     : str  YYYY-MM-DD
        subject_type: str  "subject1" | "subject2" | "subject3"
        """
        date_from = filters.get("date_from", str(date.today()))
        date_to = filters.get("date_to", str(date.today()))
        subject_type = filters.get("subject_type", "subject1")

        payload = {
            "queryCriteria": {
                "subjectType": subject_type,
                "type": "incremental",
                "acquisitionTimestampThresholdFrom": f"{date_from}T00:00:00.000Z",
                "acquisitionTimestampThresholdTo": f"{date_to}T23:59:59.999Z",
            }
        }
        result = await self._client.query_invoices(payload)
        return result.get("invoiceHeaderList", [])  # type: ignore[return-value]

    async def healthcheck(self) -> dict[str, Any]:
        try:
            resp = await self._client._request("GET", "/common/Status")
            return {"status": "ok", "ksef_response": resp.json()}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}
