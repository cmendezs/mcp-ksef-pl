"""FA(2) XML parser — converts KSeF XML into a Python dict and InvoiceDocument."""

from __future__ import annotations

from typing import Any

from mcp_einvoicing_core import (
    BaseDocumentParser,
    InvoiceDocument,
    InvoiceLineItem,
    InvoiceParty,
    PartyAddress,
    TaxIdentifier,
    ValidationError,
    VATSummary,
)
from mcp_einvoicing_core.xml_utils import safe_fromstring

_FA2_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"
_NS_MAP = {"fa": _FA2_NS}


def _load_etree() -> Any:
    try:
        from lxml import etree  # type: ignore[import]

        return etree
    except ImportError:
        msg = "lxml is required for FA(2) XML parsing. Install it with: pip install lxml"
        raise ValidationError(msg)


def _text(element: Any, xpath: str, ns: dict[str, str]) -> str:
    nodes = element.xpath(xpath, namespaces=ns)
    return nodes[0].text.strip() if nodes and nodes[0].text else ""


def _parse_party(el: Any, ns: dict[str, str]) -> dict[str, Any]:
    return {
        "nip": _text(el, ".//fa:NIP", ns),
        "vat_ue_code": _text(el, ".//fa:KodUE", ns),
        "vat_ue_nr": _text(el, ".//fa:NrVatUE", ns),
        "name": _text(el, ".//fa:Nazwa", ns),
        "address": {
            "country": _text(el, ".//fa:KodKraju", ns),
            "street": _text(el, ".//fa:AdresL1", ns),
            "postal_code": _text(el, ".//fa:KodPocztowy", ns),
            "city": _text(el, ".//fa:Miejscowosc", ns),
            "province": _text(el, ".//fa:Wojewodztwo", ns),
        },
    }


class FA2Parser(BaseDocumentParser):
    """Parses KSeF FA(2) XML documents."""

    async def parse(self, document: str) -> dict[str, Any]:
        root = safe_fromstring(document.encode())
        ns = _NS_MAP

        schema_version = root.findtext(f"{{{_FA2_NS}}}Naglowek/{{{_FA2_NS}}}KodFormularza") or ""
        header = {
            "schema_version": schema_version,
            "created_at": _text(root, "fa:Naglowek/fa:DataWytworzenieFa", ns),
            "system_info": _text(root, "fa:Naglowek/fa:SystemInfo", ns),
        }

        seller_els = root.xpath("fa:Podmiot1", namespaces=ns)
        buyer_els = root.xpath("fa:Podmiot2", namespaces=ns)

        fa_el = root.xpath("fa:Fa", namespaces=ns)
        fa = fa_el[0] if fa_el else root

        lines = []
        for row in fa.xpath("fa:FaWiersze/fa:FaWiersz", namespaces=ns):
            lines.append(
                {
                    "line_number": _text(row, "fa:NrWierszaFa", ns),
                    "description": _text(row, "fa:P_7", ns),
                    "unit": _text(row, "fa:P_8A", ns),
                    "quantity": _text(row, "fa:P_8B", ns),
                    "unit_price_net": _text(row, "fa:P_9A", ns),
                    "line_total_net": _text(row, "fa:P_11", ns),
                    "vat_rate": _text(row, "fa:P_12", ns),
                    "vat_exemption_code": _text(row, "fa:P_12_XII", ns),
                }
            )

        return {
            "header": header,
            "seller": _parse_party(seller_els[0], ns) if seller_els else {},
            "buyer": _parse_party(buyer_els[0], ns) if buyer_els else {},
            "invoice": {
                "currency": _text(fa, "fa:KodWaluty", ns),
                "date": _text(fa, "fa:P_1", ns),
                "number": _text(fa, "fa:P_2", ns),
                "due_date": _text(fa, "fa:P_6", ns),
                "net_23": _text(fa, "fa:P_13_1", ns),
                "vat_23": _text(fa, "fa:P_14_1", ns),
                "net_8": _text(fa, "fa:P_13_2", ns),
                "vat_8": _text(fa, "fa:P_14_2", ns),
                "net_5": _text(fa, "fa:P_13_3", ns),
                "vat_5": _text(fa, "fa:P_14_3", ns),
                "net_0": _text(fa, "fa:P_13_4", ns),
                "vat_0": _text(fa, "fa:P_14_4", ns),
                "net_exempt": _text(fa, "fa:P_13_5", ns),
                "gross_total": _text(fa, "fa:P_15", ns),
                "note": _text(fa, "fa:StopkaFaktury", ns),
            },
            "lines": lines,
        }

    async def to_invoice_document(self, document: str) -> InvoiceDocument:
        from decimal import Decimal

        data = await self.parse(document)
        inv = data["invoice"]
        s = data["seller"]
        b = data["buyer"]

        def _party(p: dict[str, Any]) -> InvoiceParty:
            addr = p.get("address", {})
            return InvoiceParty(
                tax_id=TaxIdentifier(
                    country_code=addr.get("country", "PL"),
                    identifier=p.get("nip", ""),
                ),
                name=p.get("name", ""),
                address=PartyAddress(
                    street=addr.get("street", ""),
                    postal_code=addr.get("postal_code", ""),
                    city=addr.get("city", ""),
                    country_code=addr.get("country", "PL"),
                    province=addr.get("province") or None,
                ),
            )

        vat_summary: list[VATSummary] = []
        for rate, net_key, vat_key in [
            (Decimal("23"), "net_23", "vat_23"),
            (Decimal("8"), "net_8", "vat_8"),
            (Decimal("5"), "net_5", "vat_5"),
            (Decimal("0"), "net_0", "vat_0"),
        ]:
            net_str = inv.get(net_key, "")
            if net_str:
                vat_summary.append(
                    VATSummary(
                        vat_rate=rate,
                        taxable_base=Decimal(net_str),
                        vat_amount=Decimal(inv.get(vat_key, "0") or "0"),
                    )
                )

        lines: list[InvoiceLineItem] = []
        for i, row in enumerate(data["lines"], start=1):
            lines.append(
                InvoiceLineItem(
                    line_number=int(row.get("line_number") or i),
                    description=row.get("description", ""),
                    quantity=Decimal(row.get("quantity", "1")),
                    unit_of_measure=row.get("unit", "szt"),
                    unit_price=Decimal(row.get("unit_price_net", "0")),
                    total_price=Decimal(row.get("line_total_net", "0")),
                    vat_rate=Decimal(row.get("vat_rate", "23")),
                    vat_exemption_code=row.get("vat_exemption_code") or None,
                    currency=inv.get("currency", "PLN"),
                )
            )

        return InvoiceDocument(
            document_type="INVOICE",
            date=inv.get("date", ""),
            number=inv.get("number", ""),
            currency=inv.get("currency", "PLN"),
            transmission_format="KSeF-FA2",
            seller=_party(s),
            buyer=_party(b),
            lines=lines,
            vat_summary=vat_summary,
            note=inv.get("note") or None,
        )
