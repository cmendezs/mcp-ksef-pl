"""Peppol BIS 3.0 UBL 2.1 serializer for Poland (PL-CORE-1).

Subclasses EN16931UBLSerializer from mcp-einvoicing-core. Scoped to the
Peppol BIS 3.0 cross-border profile only; KSeF FA(2)/FA(3) serialization
remains in generator.py.

Key overrides vs the core base:
- _build_party: resolves KSeFParty.nip → PL{nip} CompanyID and guards
  against Optional address (cross-border parties without a PL postal address)

ProfileID (BT-23) emission is delegated to the core serializer via
EN16931Invoice.business_process (core v1.15.0, PL-PEP-1) — no local XML
injection override needed. ``serialize()`` sets ``business_process`` when the
caller has not already set it, to preserve this class's prior auto-inject
behaviour.
"""

from __future__ import annotations

from lxml import etree
from mcp_einvoicing_core.en16931 import EN16931Address, EN16931Party
from mcp_einvoicing_core.wire_formats import EN16931UBLSerializer

from mcp_ksef_pl.models import KSeFInvoice, KSeFParty

_PEPPOL_CUSTOMIZATION_ID = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)
_PEPPOL_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"


def _resolve_vat_id(party: KSeFParty) -> str | None:
    if party.vat_id:
        return party.vat_id
    if party.nip:
        return f"PL{party.nip}"
    if party.eu_vat_country and party.eu_vat_id:
        return f"{party.eu_vat_country}{party.eu_vat_id}"
    return None


class KSeFPeppolUBLSerializer(EN16931UBLSerializer):
    """UBL 2.1 serializer for Peppol BIS 3.0 cross-border invoices (Poland).

    Usage::

        xml_bytes = KSeFPeppolUBLSerializer().serialize(invoice)

    The caller must set ``invoice.profile`` to the Peppol BIS 3.0 CustomizationID URN
    (``urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0``).
    ProfileID is injected automatically.
    """

    def serialize(self, invoice: KSeFInvoice) -> bytes:
        if not invoice.business_process:
            invoice.business_process = _PEPPOL_PROFILE_ID
        root = self._build_root(invoice)
        return self._to_bytes(root)

    def _build_party(self, parent: etree._Element, wrapper: str, party: EN16931Party) -> None:
        if not isinstance(party, KSeFParty):
            super()._build_party(parent, wrapper, party)
            return

        effective_address = party.address or EN16931Address(
            line_one="", city="", postcode="", country_code="PL"
        )
        proxy = EN16931Party(
            name=party.name,
            address=effective_address,
            vat_id=_resolve_vat_id(party),
            electronic_address=party.electronic_address,
            electronic_address_scheme=party.electronic_address_scheme,
            contact_name=party.contact_name,
            contact_phone=party.contact_phone,
            contact_email=party.contact_email,
        )
        super()._build_party(parent, wrapper, proxy)
