"""Peppol BIS Billing 3.0 / EN 16931 UBL 2.1 invoice generator for Poland.

Delegates to core EN16931UBLSerializer for the full EN 16931 field set.
The only PL-specific override is injecting <cbc:ProfileID> which the core
serializer does not emit.
"""

from lxml import etree
from mcp_einvoicing_core import BaseDocumentGenerator, DocumentGenerationError
from mcp_einvoicing_core.en16931 import EN16931Invoice
from mcp_einvoicing_core.wire_formats import _CBC, EN16931UBLSerializer, _q

from mcp_ksef_pl.models import KSeFInvoice

_PEPPOL_BIS3_CUSTOMIZATION_ID = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)
_PEPPOL_BIS3_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"


class _PLUBLSerializer(EN16931UBLSerializer):
    """Polish Peppol BIS 3.0 / EN 16931 UBL 2.1 serializer."""

    def _build_root(self, invoice: EN16931Invoice) -> etree._Element:
        root = super()._build_root(invoice)
        customization_el = root.find(_q(_CBC, "CustomizationID"))
        if customization_el is not None:
            profile_el = etree.Element(_q(_CBC, "ProfileID"))
            profile_el.text = _PEPPOL_BIS3_PROFILE_ID
            customization_el.addnext(profile_el)
        return root


class PeppolUBLGenerator(BaseDocumentGenerator[KSeFInvoice]):
    """Generates Peppol BIS Billing 3.0 UBL 2.1 invoices (EN 16931)."""

    def get_format_name(self) -> str:
        return "Peppol-BIS-3.0-UBL"

    def get_country_code(self) -> str:
        return "PL"

    async def generate(self, invoice: KSeFInvoice) -> str:
        try:
            invoice.profile = _PEPPOL_BIS3_CUSTOMIZATION_ID
            return _PLUBLSerializer().serialize(invoice).decode("utf-8")
        except DocumentGenerationError:
            raise
        except Exception as exc:
            raise DocumentGenerationError(
                f"Peppol UBL generation failed: {exc}"
            ) from exc
