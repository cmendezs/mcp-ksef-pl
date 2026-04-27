"""FA(2) XML generator for the Polish KSeF national e-invoicing format.

Schema namespace: http://crd.gov.pl/wzor/2023/06/29/12648/
Schema version:   FA (2) / wariant 2
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from mcp_einvoicing_core import (
    BaseDocumentGenerator,
    DocumentGenerationError,
    InvoiceDocument,
    InvoiceParty,
    VATSummary,
    format_amount,
    xml_escape,
    xml_optional,
)

_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"
_SYSTEM_INFO = "mcp-ksef-pl/0.1.0"

# Mapping from VAT rate (Decimal) to FA(2) P_13_x / P_14_x field index
_VAT_RATE_FIELD: dict[str, int] = {
    "23": 1,
    "8": 2,
    "5": 3,
    "0": 4,
}
_EXEMPT_FIELD = 5  # P_13_5: exempt (zwolnienie z VAT)


def _d(value: Decimal) -> str:
    """Round to 2 dp and format as string."""
    return format_amount(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _party_block(party: InvoiceParty, tag: str) -> str:
    """Render a Podmiot1 (seller) or Podmiot2 (buyer) XML block."""
    name = party.name or f"{party.first_name or ''} {party.last_name or ''}".strip()
    nip = party.tax_id.identifier if party.tax_id.country_code.upper() == "PL" else ""

    id_block = f"<NIP>{xml_escape(nip)}</NIP>\n" if nip else ""
    if party.alt_tax_id:
        id_block += f"<KodUE>{xml_escape(party.tax_id.country_code.upper())}</KodUE>\n"
        id_block += f"<NrVatUE>{xml_escape(party.alt_tax_id.identifier)}</NrVatUE>\n"
    id_block += f"<Nazwa>{xml_escape(name)}</Nazwa>\n"

    addr_block = ""
    if party.address:
        a = party.address
        addr_block = (
            f"<Adres>\n"
            f"  <KodKraju>{xml_escape(a.country_code.upper())}</KodKraju>\n"
            f"  <AdresL1>{xml_escape(a.street or '')}</AdresL1>\n"
            + (f"  <KodPocztowy>{xml_escape(a.postal_code)}</KodPocztowy>\n" if a.postal_code else "")
            + f"  <Miejscowosc>{xml_escape(a.city or '')}</Miejscowosc>\n"
            + (f"  <Wojewodztwo>{xml_escape(a.province)}</Wojewodztwo>\n" if a.province else "")
            + f"</Adres>\n"
        )

    return (
        f"<{tag}>\n"
        f"  <DaneIdentyfikacyjne>\n"
        f"    {id_block.strip()}\n"
        f"  </DaneIdentyfikacyjne>\n"
        f"  {addr_block.strip()}\n"
        f"</{tag}>\n"
    )


def _vat_summary_fields(summaries: list[VATSummary]) -> str:
    """Render P_13_x / P_14_x / P_15 fields from VAT summary list."""
    fields: dict[str, str] = {}
    total_gross = Decimal("0")

    for s in summaries:
        rate_str = str(int(s.vat_rate)) if s.vat_rate == int(s.vat_rate) else str(s.vat_rate)
        idx = _VAT_RATE_FIELD.get(rate_str)

        if idx is not None:
            fields[f"P_13_{idx}"] = _d(s.taxable_base)
            if s.vat_amount > 0:
                fields[f"P_14_{idx}"] = _d(s.vat_amount)
            total_gross += s.taxable_base + s.vat_amount
        elif s.vat_exemption_code:
            # Exempt
            fields["P_13_5"] = _d(s.taxable_base)
            total_gross += s.taxable_base
        else:
            # Unknown rate — put in field index 1 (23%) as a fallback
            fields["P_13_1"] = _d(s.taxable_base)
            fields["P_14_1"] = _d(s.vat_amount)
            total_gross += s.taxable_base + s.vat_amount

    fields["P_15"] = _d(total_gross)

    return "\n".join(f"<{k}>{v}</{k}>" for k, v in fields.items())


def _invoice_lines(invoice: InvoiceDocument) -> str:
    rows = []
    for line in invoice.lines:
        rate_str = str(int(line.vat_rate)) if line.vat_rate == int(line.vat_rate) else str(line.vat_rate)
        rows.append(
            f"  <FaWiersz>\n"
            f"    <NrWierszaFa>{line.line_number}</NrWierszaFa>\n"
            f"    <P_7>{xml_escape(line.description)}</P_7>\n"
            f"    <P_8A>{xml_escape(line.unit_of_measure or 'szt')}</P_8A>\n"
            f"    <P_8B>{format_amount(line.quantity)}</P_8B>\n"
            f"    <P_9A>{_d(line.unit_price)}</P_9A>\n"
            f"    <P_11>{_d(line.total_price)}</P_11>\n"
            f"    <P_12>{xml_escape(rate_str)}</P_12>\n"
            + (f"    <P_12_XII>{xml_escape(line.vat_exemption_code)}</P_12_XII>\n" if line.vat_exemption_code else "")
            + f"  </FaWiersz>\n"
        )
    return "<FaWiersze>\n" + "".join(rows) + "</FaWiersze>\n"


def _payment_block(invoice: InvoiceDocument) -> str:
    if not invoice.payment:
        return ""
    p = invoice.payment
    parts = []
    if p.due_date:
        parts.append(f"<P_6>{xml_escape(str(p.due_date))}</P_6>")
    if p.iban:
        parts.append(f"<RachunekBankowy><NrRB>{xml_escape(p.iban)}</NrRB></RachunekBankowy>")
    return "\n".join(parts)


class FA2Generator(BaseDocumentGenerator):
    """Generates KSeF FA(2) XML invoices from InvoiceDocument instances."""

    def get_format_name(self) -> str:
        return "FA(2)"

    def get_country_code(self) -> str:
        return "PL"

    def get_namespace(self) -> str:
        return _NS

    async def generate(self, invoice: InvoiceDocument) -> str:
        try:
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            vat_fields = _vat_summary_fields(invoice.vat_summary or [])
            payment = _payment_block(invoice)

            xml = (
                f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<Faktura xmlns="{_NS}"\n'
                f'         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
                f"  <Naglowek>\n"
                f'    <KodFormularza kodSystemowy="FA (2)" wersjaSchemy="1-0E">FA</KodFormularza>\n'
                f"    <WariantFormularza>2</WariantFormularza>\n"
                f"    <DataWytworzenieFa>{now_utc}</DataWytworzenieFa>\n"
                f"    <SystemInfo>{xml_escape(_SYSTEM_INFO)}</SystemInfo>\n"
                f"  </Naglowek>\n"
                f"  {_party_block(invoice.seller, 'Podmiot1').strip()}\n"
                f"  {_party_block(invoice.buyer, 'Podmiot2').strip()}\n"
                f"  <Fa>\n"
                f"    <KodWaluty>{xml_escape(invoice.currency)}</KodWaluty>\n"
                f"    <P_1>{xml_escape(str(invoice.date))}</P_1>\n"
                f"    <P_2>{xml_escape(invoice.number)}</P_2>\n"
                f"    {vat_fields}\n"
                f"    {payment}\n"
                f"    <Adnotacje>\n"
                f"      <P_16>2</P_16>\n"
                f"      <P_17>2</P_17>\n"
                f"      <P_18>2</P_18>\n"
                f"      <P_18A>2</P_18A>\n"
                f"      <P_23>2</P_23>\n"
                f"    </Adnotacje>\n"
                f"    {_invoice_lines(invoice).strip()}\n"
                + (f"    <StopkaFaktury>{xml_escape(invoice.note)}</StopkaFaktury>\n" if invoice.note else "")
                + f"  </Fa>\n"
                f"</Faktura>\n"
            )
            return xml
        except Exception as exc:
            raise DocumentGenerationError(f"FA(2) generation failed: {exc}") from exc
