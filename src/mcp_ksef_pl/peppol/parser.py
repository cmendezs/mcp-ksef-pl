"""Peppol BIS 3.0 UBL 2.1 parser for Poland (PL-CORE-1).

Subclasses EN16931UBLParser from mcp-einvoicing-core. Scoped to the
Peppol BIS 3.0 cross-border profile only.

Returns KSeFInvoice with KSeFParty objects. NIP is extracted from the
parsed vat_id when the prefix is "PL" and the total length is 12 chars
(e.g. "PL5261040828" → nip="5261040828"). Other country codes are split
into eu_vat_country / eu_vat_id.
"""

from __future__ import annotations

from mcp_einvoicing_core.en16931 import EN16931Party
from mcp_einvoicing_core.wire_formats import EN16931UBLParser

from mcp_ksef_pl.models import KSeFInvoice


def _to_ksef_party_dict(party: EN16931Party) -> dict:
    nip: str | None = None
    eu_vat_country: str | None = None
    eu_vat_id: str | None = None
    vat = party.vat_id
    if vat and len(vat) > 2:
        prefix = vat[:2].upper()
        suffix = vat[2:]
        if prefix == "PL" and len(suffix) == 10:
            nip = suffix
        else:
            eu_vat_country = prefix
            eu_vat_id = suffix
    d = party.model_dump()
    d.update(nip=nip, eu_vat_country=eu_vat_country, eu_vat_id=eu_vat_id, gln=None)
    return d


class KSeFPeppolUBLParser(EN16931UBLParser):
    """Peppol BIS 3.0 UBL parser for Poland.

    Parses a UBL 2.1 Invoice or CreditNote into a KSeFInvoice with
    KSeFParty sellers and buyers.

    Usage::

        invoice = KSeFPeppolUBLParser().parse(xml_bytes)
    """

    def parse(self, xml_bytes: bytes) -> KSeFInvoice:
        base = super().parse(xml_bytes)
        data = base.model_dump()
        data["seller"] = _to_ksef_party_dict(base.seller)
        data["buyer"] = _to_ksef_party_dict(base.buyer)
        data.setdefault("numer_ksef", None)
        return KSeFInvoice.model_validate(data)
