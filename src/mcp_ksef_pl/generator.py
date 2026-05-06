"""XML generators for Polish KSeF electronic invoice formats.

FA(2) — legacy format (KSeF v1)
  Schema namespace: http://crd.gov.pl/wzor/2023/06/29/12648/
  Schema version:   FA (2) / wariant 2
  XSD reference:    specs/schemat_FA(2)_v1-0E.xsd

FA(3) — current format required by KSeF API v2
  Schema namespace: http://crd.gov.pl/wzor/2025/06/25/13775/
  Schema version:   FA (3) / wariant 3
  XSD reference:    specs/schemat_FA(3)_v1-0E.xsd

FA(3) structural differences from FA(2) that are implemented here:
  - New XML namespace
  - KodFormularza kodSystemowy="FA (3)", WariantFormularza=3
  - DataWytworzeniaFa (corrected spelling; FA(2) generator has typo DataWytworzenieFa)
  - TAdres uses only KodKraju + AdresL1 + optional AdresL2; no KodPocztowy/Miejscowosc
  - Podmiot2 (buyer) gains two mandatory flags: <JST>2</JST> and <GV>2</GV>
  - Adnotacje includes mandatory sub-elements: Zwolnienie, NoweSrodkiTransportu, PMarzy
  - RodzajFaktury [1..1] is mandatory directly after Adnotacje in <Fa>
  - FaWiersz items are direct children of <Fa>; no <FaWiersze> wrapper
  - Optional note goes in <Stopka><Informacje><StopkaFaktury>, not inside <Fa>
"""

import datetime as _dt
from decimal import ROUND_HALF_UP, Decimal

from mcp_einvoicing_core import (
    BaseDocumentGenerator,
    DocumentGenerationError,
    InvoiceDocument,
    InvoiceParty,
    VATSummary,
    format_amount,
)
from mcp_einvoicing_core.xml_utils import xml_escape

_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"
_NS3 = "http://crd.gov.pl/wzor/2025/06/25/13775/"
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
            now_utc = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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


# ---------------------------------------------------------------------------
# FA(3) helpers
# ---------------------------------------------------------------------------


def _adres_block(party: InvoiceParty) -> str:
    """Build a TAdres block (KodKraju + AdresL1 + optional AdresL2).

    TAdres in both FA(2) and FA(3) XSD contains only KodKraju, AdresL1, AdresL2,
    and GLN.  Structured postal/city fields are composed into AdresL1.
    """
    if not party.address:
        return ""
    a = party.address

    parts = [a.street or "", a.postal_code or "", a.city or ""]
    adres_l1 = " ".join(p for p in parts if p).strip(", ") or xml_escape(party.name or "")

    lines = [
        "<Adres>",
        f"  <KodKraju>{xml_escape(a.country_code.upper())}</KodKraju>",
        f"  <AdresL1>{xml_escape(adres_l1)}</AdresL1>",
    ]
    if a.province:
        # AdresL2 is optional — use for province/region when present
        lines.append(f"  <AdresL2>{xml_escape(a.province)}</AdresL2>")
    lines.append("</Adres>")
    return "\n".join(lines)


def _fa3_seller_block(seller: InvoiceParty) -> str:
    """Build <Podmiot1> for FA(3)."""
    name = seller.name or f"{seller.first_name or ''} {seller.last_name or ''}".strip()
    nip = seller.tax_id.identifier if seller.tax_id.country_code.upper() == "PL" else ""

    id_lines = []
    if nip:
        id_lines.append(f"<NIP>{xml_escape(nip)}</NIP>")
    if seller.alt_tax_id:
        id_lines.append(f"<KodUE>{xml_escape(seller.tax_id.country_code.upper())}</KodUE>")
        id_lines.append(f"<NrVatUE>{xml_escape(seller.alt_tax_id.identifier)}</NrVatUE>")
    id_lines.append(f"<Nazwa>{xml_escape(name)}</Nazwa>")

    adres = _adres_block(seller)

    lines = ["<Podmiot1>", "  <DaneIdentyfikacyjne>"]
    for il in id_lines:
        lines.append(f"    {il}")
    lines.append("  </DaneIdentyfikacyjne>")
    if adres:
        for al in adres.splitlines():
            lines.append(f"  {al}")
    lines.append("</Podmiot1>")
    return "\n".join(lines)


def _fa3_buyer_block(buyer: InvoiceParty) -> str:
    """Build <Podmiot2> for FA(3), including mandatory JST and GV flags.

    JST=2 means the invoice does not concern a subordinate local-government unit.
    GV=2  means the invoice does not concern a VAT-group member.
    Both default to 2 (not applicable) for standard B2B invoices.
    """
    name = buyer.name or f"{buyer.first_name or ''} {buyer.last_name or ''}".strip()
    nip = buyer.tax_id.identifier if buyer.tax_id.country_code.upper() == "PL" else ""

    id_lines: list[str] = []
    if nip:
        id_lines.append(f"<NIP>{xml_escape(nip)}</NIP>")
    elif buyer.alt_tax_id:
        id_lines.append(f"<KodUE>{xml_escape(buyer.tax_id.country_code.upper())}</KodUE>")
        id_lines.append(f"<NrVatUE>{xml_escape(buyer.alt_tax_id.identifier)}</NrVatUE>")
    else:
        id_lines.append("<BrakID>1</BrakID>")
    id_lines.append(f"<Nazwa>{xml_escape(name)}</Nazwa>")

    adres = _adres_block(buyer)

    lines = ["<Podmiot2>", "  <DaneIdentyfikacyjne>"]
    for il in id_lines:
        lines.append(f"    {il}")
    lines.append("  </DaneIdentyfikacyjne>")
    if adres:
        for al in adres.splitlines():
            lines.append(f"  {al}")
    lines.append("  <JST>2</JST>")
    lines.append("  <GV>2</GV>")
    lines.append("</Podmiot2>")
    return "\n".join(lines)


def _fa3_vat_fields(summaries: list[VATSummary]) -> tuple[str, str]:
    """Return (vat_lines_xml, p15_xml) from the VAT summary list.

    The XSD groups (P_13_x, P_14_x) into optional inner sequences per rate band.
    Only bands with actual amounts are emitted.  P_15 (total gross) is always
    required.
    """
    band_lines: list[str] = []
    total_gross = Decimal("0")

    for s in summaries:
        rate_str = str(int(s.vat_rate)) if s.vat_rate == int(s.vat_rate) else str(s.vat_rate)
        idx = _VAT_RATE_FIELD.get(rate_str)

        if idx is not None:
            band_lines.append(f"<P_13_{idx}>{_d(s.taxable_base)}</P_13_{idx}>")
            if s.vat_amount > 0:
                band_lines.append(f"<P_14_{idx}>{_d(s.vat_amount)}</P_14_{idx}>")
            total_gross += s.taxable_base + s.vat_amount
        elif s.vat_exemption_code:
            band_lines.append(f"<P_13_5>{_d(s.taxable_base)}</P_13_5>")
            total_gross += s.taxable_base
        else:
            band_lines.append(f"<P_13_1>{_d(s.taxable_base)}</P_13_1>")
            band_lines.append(f"<P_14_1>{_d(s.vat_amount)}</P_14_1>")
            total_gross += s.taxable_base + s.vat_amount

    vat_xml = "\n".join(band_lines)
    p15_xml = f"<P_15>{_d(total_gross)}</P_15>"
    return vat_xml, p15_xml


def _fa3_adnotacje() -> str:
    """Return the mandatory <Adnotacje> block for a standard VAT invoice.

    All annotations default to 'not applicable' (2 / N values):
      P_16–P_18A, P_23  → 2 (not applicable for this invoice)
      Zwolnienie         → P_19N=1 (no VAT exemption)
      NoweSrodkiTransp.  → P_22N=1 (no new means of transport)
      PMarzy             → P_PMarzyN=1 (no margin scheme)
    """
    return (
        "<Adnotacje>\n"
        "  <P_16>2</P_16>\n"
        "  <P_17>2</P_17>\n"
        "  <P_18>2</P_18>\n"
        "  <P_18A>2</P_18A>\n"
        "  <Zwolnienie>\n"
        "    <P_19N>1</P_19N>\n"
        "  </Zwolnienie>\n"
        "  <NoweSrodkiTransportu>\n"
        "    <P_22N>1</P_22N>\n"
        "  </NoweSrodkiTransportu>\n"
        "  <P_23>2</P_23>\n"
        "  <PMarzy>\n"
        "    <P_PMarzyN>1</P_PMarzyN>\n"
        "  </PMarzy>\n"
        "</Adnotacje>"
    )


def _fa3_wiersz_lines(invoice: InvoiceDocument) -> str:
    """Return repeated <FaWiersz> elements (no wrapper in FA(3))."""
    rows: list[str] = []
    for line in invoice.lines:
        rate_str = (
            str(int(line.vat_rate))
            if line.vat_rate == int(line.vat_rate)
            else str(line.vat_rate)
        )
        row_lines = [
            "<FaWiersz>",
            f"  <NrWierszaFa>{line.line_number}</NrWierszaFa>",
            f"  <P_7>{xml_escape(line.description)}</P_7>",
            f"  <P_8A>{xml_escape(line.unit_of_measure or 'szt')}</P_8A>",
            f"  <P_8B>{format_amount(line.quantity)}</P_8B>",
            f"  <P_9A>{_d(line.unit_price)}</P_9A>",
            f"  <P_11>{_d(line.total_price)}</P_11>",
            f"  <P_12>{xml_escape(rate_str)}</P_12>",
        ]
        if line.vat_exemption_code:
            row_lines.append(
                f"  <P_12_XII>{xml_escape(line.vat_exemption_code)}</P_12_XII>"
            )
        row_lines.append("</FaWiersz>")
        rows.append("\n".join(row_lines))
    return "\n".join(rows)


def _fa3_platnosc_block(invoice: InvoiceDocument) -> str:
    """Build an optional <Platnosc> block when IBAN or due_date is present.

    Implements the minimum viable payment section:
      - RachunekBankowy with IBAN (when provided)
      - TerminPlatnosci with due date and FormaPlatnosci=6 (wire transfer)

    FormaPlatnosci=6 (przelew bankowy) is the standard default for B2B
    invoices; override by passing full XML if another payment form is needed.
    """
    if not invoice.payment:
        return ""
    p = invoice.payment
    if not p.iban and not p.due_date:
        return ""

    parts = ["<Platnosc>"]
    if p.due_date:
        parts.append(
            f"  <TerminPlatnosci>\n"
            f"    <Termin>{xml_escape(str(p.due_date))}</Termin>\n"
            f"    <FormaPlatnosci>6</FormaPlatnosci>\n"
            f"  </TerminPlatnosci>"
        )
    if p.iban:
        parts.append(
            f"  <RachunekBankowy>\n"
            f"    <NrRB>{xml_escape(p.iban)}</NrRB>\n"
            f"  </RachunekBankowy>"
        )
    parts.append("</Platnosc>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# FA(3) generator
# ---------------------------------------------------------------------------


class FA3Generator(BaseDocumentGenerator):
    """Generates KSeF FA(3) XML invoices for use with KSeF API v2.

    FA(3) is required for all new invoice submissions via KSeF API v2 online
    or batch sessions.  FA(2) is not accepted for new submissions.

    Schema: http://crd.gov.pl/wzor/2025/06/25/13775/
    XSD:    specs/schemat_FA(3)_v1-0E.xsd (reference copy; not bundled for validation)
    """

    def get_format_name(self) -> str:
        return "FA(3)"

    def get_country_code(self) -> str:
        return "PL"

    def get_namespace(self) -> str:
        return _NS3

    async def generate(self, invoice: InvoiceDocument) -> str:  # noqa: C901
        """Generate a KSeF-compliant FA(3) XML invoice.

        Produces a standard VAT invoice (RodzajFaktury=VAT).  Correction,
        advance, and settlement invoice types are not yet supported.

        Args:
            invoice: Structured invoice data.  seller.tax_id must be a Polish
                     NIP (10 digits).  buyer.tax_id may be a Polish NIP, a
                     EU VAT number, or absent (BrakID).

        Returns:
            UTF-8 FA(3) XML string ready to be passed to submit_invoice_to_ksef.
        """
        try:
            now_utc = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            vat_xml, p15_xml = _fa3_vat_fields(invoice.vat_summary or [])
            platnosc = _fa3_platnosc_block(invoice)

            parts: list[str] = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                f'<Faktura xmlns="{_NS3}">',
                # --- Naglowek ---
                "  <Naglowek>",
                '    <KodFormularza kodSystemowy="FA (3)" wersjaSchemy="1-0E">FA</KodFormularza>',
                "    <WariantFormularza>3</WariantFormularza>",
                f"    <DataWytworzeniaFa>{now_utc}</DataWytworzeniaFa>",
                f"    <SystemInfo>{xml_escape(_SYSTEM_INFO)}</SystemInfo>",
                "  </Naglowek>",
                # --- Podmiot1 (seller) ---
                f"  {_fa3_seller_block(invoice.seller).replace(chr(10), chr(10) + '  ').strip()}",
                # --- Podmiot2 (buyer) ---
                f"  {_fa3_buyer_block(invoice.buyer).replace(chr(10), chr(10) + '  ').strip()}",
                # --- Fa ---
                "  <Fa>",
                f"    <KodWaluty>{xml_escape(invoice.currency)}</KodWaluty>",
                f"    <P_1>{xml_escape(str(invoice.date))}</P_1>",
                f"    <P_2>{xml_escape(invoice.number)}</P_2>",
            ]

            # VAT rate bands (only non-zero bands are emitted)
            if vat_xml:
                for vl in vat_xml.splitlines():
                    parts.append(f"    {vl}")

            # Total gross (mandatory)
            parts.append(f"    {p15_xml}")

            # Adnotacje (mandatory, all defaults)
            for al in _fa3_adnotacje().splitlines():
                parts.append(f"    {al}")

            # RodzajFaktury (mandatory — VAT for standard invoices)
            parts.append("    <RodzajFaktury>VAT</RodzajFaktury>")

            # Invoice lines (direct FaWiersz children, no wrapper)
            if invoice.lines:
                for wl in _fa3_wiersz_lines(invoice).splitlines():
                    parts.append(f"    {wl}")

            # Payment block (optional)
            if platnosc:
                for pl in platnosc.splitlines():
                    parts.append(f"    {pl}")

            parts.append("  </Fa>")

            # Stopka — optional note (correct location per XSD)
            if invoice.note:
                parts += [
                    "  <Stopka>",
                    "    <Informacje>",
                    f"      <StopkaFaktury>{xml_escape(invoice.note)}</StopkaFaktury>",
                    "    </Informacje>",
                    "  </Stopka>",
                ]

            parts.append("</Faktura>")
            return "\n".join(parts) + "\n"

        except Exception as exc:
            raise DocumentGenerationError(f"FA(3) generation failed: {exc}") from exc
