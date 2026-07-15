"""Peppol BIS Billing 3.0 / EN 16931 UBL 2.1 invoice generator for Poland.

Delegates to core EN16931UBLSerializer for the full EN 16931 field set,
including <cbc:ProfileID> emission from EN16931Invoice.business_process
(core v1.15.0, PL-PEP-1) — no local override needed.
"""

from mcp_einvoicing_core import BaseDocumentGenerator, DocumentGenerationError
from mcp_einvoicing_core.wire_formats import EN16931UBLSerializer

from mcp_ksef_pl.models import KSeFInvoice

_PEPPOL_BIS3_CUSTOMIZATION_ID = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)
_PEPPOL_BIS3_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"


class PeppolUBLGenerator(BaseDocumentGenerator[KSeFInvoice]):
    """Generates Peppol BIS Billing 3.0 UBL 2.1 invoices (EN 16931)."""

    def get_format_name(self) -> str:
        return "Peppol-BIS-3.0-UBL"

    def get_country_code(self) -> str:
        return "PL"

    async def generate(self, invoice: KSeFInvoice) -> str:
        try:
            invoice.profile = _PEPPOL_BIS3_CUSTOMIZATION_ID
            invoice.business_process = _PEPPOL_BIS3_PROFILE_ID
            return EN16931UBLSerializer().serialize(invoice).decode("utf-8")
        except DocumentGenerationError:
            raise
        except Exception as exc:
            raise DocumentGenerationError(
                f"Peppol UBL generation failed: {exc}"
            ) from exc
