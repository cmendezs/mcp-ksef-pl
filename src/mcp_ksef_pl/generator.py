"""XML generators for Polish KSeF electronic invoice formats.

FA(2) — legacy format (KSeF v1)
  Schema namespace: http://crd.gov.pl/wzor/2023/06/29/12648/
  Schema version:   FA (2) / wariant 2
  XSD reference:    src/mcp_ksef_pl/schemas/schemat_FA(2)_v1-0E.xsd

FA(3) — current format required by KSeF API v2
  Schema namespace: http://crd.gov.pl/wzor/2025/06/25/13775/
  Schema version:   FA (3) / wariant 3
  XSD reference:    src/mcp_ksef_pl/schemas/schemat_FA(3)_v1-0E.xsd

FA(3) structural differences from FA(2) that are implemented here:
  - New XML namespace
  - KodFormularza kodSystemowy="FA (3)", WariantFormularza=3
  - DataWytworzeniaFa (corrected spelling; FA(2) generator has typo DataWytworzenieFa)
  - Podmiot2 (buyer) gains two mandatory flags: <JST>2</JST> and <GV>2</GV>
  - Optional note goes in <Stopka><Informacje><StopkaFaktury>, not inside <Fa>

The following were previously (incorrectly) documented as FA(3)-only additions.
Verified via lxml against both bundled XSDs: FA(2)'s TAdres, Adnotacje, and Fa
content models are identical to FA(3)'s on these points, so both generators
share the same helpers (_adres_block, _adnotacje, _*_wiersz_lines):
  - TAdres uses only KodKraju + AdresL1 + optional AdresL2 + optional GLN; no
    KodPocztowy/Miejscowosc/Wojewodztwo in either format
  - Adnotacje includes mandatory sub-elements: Zwolnienie, NoweSrodkiTransportu, PMarzy
  - RodzajFaktury [1..1] is mandatory directly after Adnotacje in <Fa>
  - FaWiersz items are direct children of <Fa> in both formats; neither uses a
    <FaWiersze> wrapper
"""

import datetime as _dt
from decimal import ROUND_HALF_UP, Decimal

from mcp_einvoicing_core import (
    BaseDocumentGenerator,
    DocumentGenerationError,
    format_amount,
)
from mcp_einvoicing_core.en16931 import EN16931Tax
from mcp_einvoicing_core.xml_utils import xml_escape

from .models import (
    KSeFAttachment,
    KSeFCorrectionRef,
    KSeFFA3Options,
    KSeFInvoice,
    KSeFParty,
    KSeFPodmiot3,
    KSeFPodmiotUpowazniony,
)

_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"
_NS3 = "http://crd.gov.pl/wzor/2025/06/25/13775/"
_SYSTEM_INFO = "mcp-ksef-pl/0.5.0"

# Mapping from VAT rate (Decimal) to FA(2) P_13_x / P_14_x field index
_VAT_RATE_FIELD: dict[str, int] = {
    "23": 1,
    "8": 2,
    "5": 3,
    "0": 4,
}
_EXEMPT_FIELD = 5  # P_13_5: exempt (zwolnienie z VAT)

# UNCL5305 category to KSeF exemption code
_KSEF_EXEMPTION: dict[str, str] = {"AE": "OO", "O": "NP", "E": "ZW"}


def _d(value: Decimal) -> str:
    """Round to 2 dp and format as string."""
    return format_amount(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _ksef_exempt_code(category: str) -> str | None:
    """Map UNCL5305 VAT category to KSeF-specific exemption code for P_12_XII."""
    return _KSEF_EXEMPTION.get(category.upper())


def _party_block(party: KSeFParty, tag: str) -> str:
    """Render a Podmiot1 (seller) or Podmiot2 (buyer) XML block.

    TAdres in the FA(2) XSD (verified via lxml against schemat_FA(2)_v1-0E.xsd)
    contains only KodKraju, AdresL1, AdresL2, and GLN — the same restricted
    shape as FA(3)'s TAdres. KodPocztowy/Miejscowosc/Wojewodztwo are not valid
    FA(2) TAdres members either; use _adres_block for both formats.
    """
    nip = party.nip or ""

    id_block = f"<NIP>{xml_escape(nip)}</NIP>\n" if nip else ""
    if party.eu_vat_country and party.eu_vat_id:
        id_block += f"<KodUE>{xml_escape(party.eu_vat_country.upper())}</KodUE>\n"
        id_block += f"<NrVatUE>{xml_escape(party.eu_vat_id)}</NrVatUE>\n"
    id_block += f"<Nazwa>{xml_escape(party.name)}</Nazwa>\n"

    addr_block = _adres_block(party)
    if addr_block:
        addr_block += "\n"

    return (
        f"<{tag}>\n"
        f"  <DaneIdentyfikacyjne>\n"
        f"    {id_block.strip()}\n"
        f"  </DaneIdentyfikacyjne>\n"
        f"  {addr_block.strip()}\n"
        f"</{tag}>\n"
    )


def _vat_summary_fields(summaries: list[EN16931Tax]) -> str:
    """Render P_13_x / P_14_x / P_15 fields from VAT summary list."""
    fields: dict[str, str] = {}
    total_gross = Decimal("0")

    for s in summaries:
        rate_str = str(int(s.rate)) if s.rate == int(s.rate) else str(s.rate)
        idx = _VAT_RATE_FIELD.get(rate_str)
        category = s.category.upper()

        if idx is not None and category in ("S", "Z"):
            # Standard rate band: use the rate-based field index
            fields[f"P_13_{idx}"] = _d(s.taxable_amount)
            if s.tax_amount > 0:
                fields[f"P_14_{idx}"] = _d(s.tax_amount)
            total_gross += s.taxable_amount + s.tax_amount
        elif category == "AE":
            fields["P_13_6_1"] = _d(s.taxable_amount)
            total_gross += s.taxable_amount
        elif category == "O":
            fields["P_13_7"] = _d(s.taxable_amount)
            total_gross += s.taxable_amount
        elif category == "E":
            # ZW (zwolnienie) and exempt categories
            fields["P_13_5"] = _d(s.taxable_amount)
            total_gross += s.taxable_amount
        else:
            raise DocumentGenerationError(
                f"Unknown standard-category VAT rate {rate_str!r} (category {category!r}); "
                "expected one of 23, 8, 5, 0."
            )

    fields["P_15"] = _d(total_gross)

    return "\n".join(f"<{k}>{v}</{k}>" for k, v in fields.items())


def _fa2_platnosc_block(invoice: KSeFInvoice) -> str:
    """Build an optional <Platnosc> block for FA(2) when IBAN or due_date is present.

    XSD <Platnosc> sequence (verified against schemat_FA(2)_v1-0E.xsd): it is a
    direct sibling of <FaWiersz>, positioned after the invoice lines (Zaplacono-choice
    not emitted here), TerminPlatnosci, FormaPlatnosci-choice, RachunekBankowy,
    RachunekBankowyFaktora, Skonto — identical shape to FA(3)'s <Platnosc>
    (see _fa3_platnosc_block), minus the FA(3)-only LinkDoPlatnosci/IPKSeF elements,
    which do not exist in the FA(2) schema. TerminPlatnosci only contains
    Termin/TerminOpis — FormaPlatnosci is a sibling element after TerminPlatnosci,
    not nested inside it. FormaPlatnosci=6 (przelew bankowy) is the standard
    default for B2B invoices.

    PL-PAY-1: previously this invoice-level due_date was (mis)emitted as a raw
    <P_6> field with an unwrapped <RachunekBankowy> spliced in before
    <RodzajFaktury>. <P_6> does exist in the schema, but it means "date of
    supply/service completion", not "payment due date" — due_date belongs in
    <Platnosc>/<TerminPlatnosci> instead.
    """
    pm = invoice.payment_means
    has_iban = pm and pm.iban
    has_due_date = invoice.due_date is not None
    if not has_iban and not has_due_date:
        return ""

    parts = ["<Platnosc>"]
    if has_due_date:
        parts.append(
            f"  <TerminPlatnosci>\n"
            f"    <Termin>{xml_escape(str(invoice.due_date))}</Termin>\n"
            f"  </TerminPlatnosci>"
        )
    parts.append("  <FormaPlatnosci>6</FormaPlatnosci>")
    if has_iban:
        parts.append(
            f"  <RachunekBankowy>\n    <NrRB>{xml_escape(pm.iban)}</NrRB>\n  </RachunekBankowy>"
        )
    parts.append("</Platnosc>")
    return "\n".join(parts)


class FA2Generator(BaseDocumentGenerator[KSeFInvoice]):
    """Generates KSeF FA(2) XML invoices from KSeFInvoice instances."""

    def get_format_name(self) -> str:
        return "FA(2)"

    def get_country_code(self) -> str:
        return "PL"

    def get_namespace(self) -> str:
        return _NS

    async def generate(self, invoice: KSeFInvoice) -> str:
        try:
            now_utc = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            vat_fields = _vat_summary_fields(invoice.tax_lines or [])
            platnosc = _fa2_platnosc_block(invoice)

            parts: list[str] = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                f'<Faktura xmlns="{_NS}"',
                '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
                "  <Naglowek>",
                '    <KodFormularza kodSystemowy="FA (2)" wersjaSchemy="1-0E">FA</KodFormularza>',
                "    <WariantFormularza>2</WariantFormularza>",
                f"    <DataWytworzeniaFa>{now_utc}</DataWytworzeniaFa>",
                f"    <SystemInfo>{xml_escape(_SYSTEM_INFO)}</SystemInfo>",
                "  </Naglowek>",
                f"  {_party_block(invoice.seller, 'Podmiot1').strip()}",
                f"  {_party_block(invoice.buyer, 'Podmiot2').strip()}",
                "  <Fa>",
                f"    <KodWaluty>{xml_escape(invoice.currency_code)}</KodWaluty>",
                f"    <P_1>{xml_escape(str(invoice.invoice_date))}</P_1>",
                f"    <P_2>{xml_escape(invoice.invoice_number)}</P_2>",
            ]
            if vat_fields:
                for vl in vat_fields.splitlines():
                    parts.append(f"    {vl}")
            for al in _adnotacje().splitlines():
                parts.append(f"    {al}")
            parts.append("    <RodzajFaktury>VAT</RodzajFaktury>")
            if invoice.line_items:
                for wl in _wiersz_lines(invoice).splitlines():
                    parts.append(f"    {wl}")
            if platnosc:
                for pl in platnosc.splitlines():
                    parts.append(f"    {pl}")
            parts.append("  </Fa>")
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
            raise DocumentGenerationError(f"FA(2) generation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# FA(3) helpers
# ---------------------------------------------------------------------------


def _adres_block(party: KSeFParty) -> str:
    """Build a TAdres block (KodKraju + AdresL1 + optional AdresL2).

    TAdres in both FA(2) and FA(3) XSD contains only KodKraju, AdresL1, AdresL2,
    and GLN.  EN16931Address.line_one is already a composed single-line address.
    """
    if not party.address:
        return ""
    a = party.address

    lines = [
        "<Adres>",
        f"  <KodKraju>{xml_escape(a.country_code.upper())}</KodKraju>",
        f"  <AdresL1>{xml_escape(a.line_one)}</AdresL1>",
    ]
    if a.region:
        # AdresL2 is optional — use for region/province when present
        lines.append(f"  <AdresL2>{xml_escape(a.region)}</AdresL2>")
    if party.gln:
        lines.append(f"  <GLN>{xml_escape(str(party.gln))}</GLN>")
    lines.append("</Adres>")
    return "\n".join(lines)


def _fa3_seller_block(seller: KSeFParty) -> str:
    """Build <Podmiot1> for FA(3)."""
    nip = seller.nip or ""

    id_lines = []
    if nip:
        id_lines.append(f"<NIP>{xml_escape(nip)}</NIP>")
    if seller.eu_vat_country and seller.eu_vat_id:
        id_lines.append(f"<KodUE>{xml_escape(seller.eu_vat_country.upper())}</KodUE>")
        id_lines.append(f"<NrVatUE>{xml_escape(seller.eu_vat_id)}</NrVatUE>")
    id_lines.append(f"<Nazwa>{xml_escape(seller.name)}</Nazwa>")

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


def _fa3_buyer_block(buyer: KSeFParty) -> str:
    """Build <Podmiot2> for FA(3), including mandatory JST and GV flags.

    JST=2 means the invoice does not concern a subordinate local-government unit.
    GV=2  means the invoice does not concern a VAT-group member.
    Both default to 2 (not applicable) for standard B2B invoices.
    """
    nip = buyer.nip or ""

    id_lines: list[str] = []
    if nip:
        id_lines.append(f"<NIP>{xml_escape(nip)}</NIP>")
    elif buyer.eu_vat_country and buyer.eu_vat_id:
        id_lines.append(f"<KodUE>{xml_escape(buyer.eu_vat_country.upper())}</KodUE>")
        id_lines.append(f"<NrVatUE>{xml_escape(buyer.eu_vat_id)}</NrVatUE>")
    else:
        id_lines.append("<BrakID>1</BrakID>")
    id_lines.append(f"<Nazwa>{xml_escape(buyer.name)}</Nazwa>")

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


def _fa3_vat_fields(summaries: list[EN16931Tax]) -> tuple[str, str]:
    """Return (vat_lines_xml, p15_xml) from the VAT summary list.

    The XSD groups (P_13_x, P_14_x) into optional inner sequences per rate band.
    Only bands with actual amounts are emitted.  P_15 (total gross) is always
    required.
    """
    band_lines: list[str] = []
    total_gross = Decimal("0")

    for s in summaries:
        rate_str = str(int(s.rate)) if s.rate == int(s.rate) else str(s.rate)
        idx = _VAT_RATE_FIELD.get(rate_str)
        category = s.category.upper()

        if idx is not None and category in ("S", "Z"):
            # Standard rate band
            band_lines.append(f"<P_13_{idx}>{_d(s.taxable_amount)}</P_13_{idx}>")
            if s.tax_amount > 0:
                band_lines.append(f"<P_14_{idx}>{_d(s.tax_amount)}</P_14_{idx}>")
            total_gross += s.taxable_amount + s.tax_amount
        elif category == "AE":
            band_lines.append(f"<P_13_6_1>{_d(s.taxable_amount)}</P_13_6_1>")
            total_gross += s.taxable_amount
        elif category == "O":
            band_lines.append(f"<P_13_7>{_d(s.taxable_amount)}</P_13_7>")
            total_gross += s.taxable_amount
        elif category == "E":
            # ZW (zwolnienie) and any exempt category
            band_lines.append(f"<P_13_5>{_d(s.taxable_amount)}</P_13_5>")
            total_gross += s.taxable_amount
        else:
            raise DocumentGenerationError(
                f"Unknown standard-category VAT rate {rate_str!r} (category {category!r}); "
                "expected one of 23, 8, 5, 0."
            )

    vat_xml = "\n".join(band_lines)
    p15_xml = f"<P_15>{_d(total_gross)}</P_15>"
    return vat_xml, p15_xml


def _adnotacje() -> str:
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


def _wiersz_lines(invoice: KSeFInvoice) -> str:
    """Return repeated <FaWiersz> elements (no wrapper in FA(3))."""
    rows: list[str] = []
    for line in invoice.line_items:
        rate_str = (
            str(int(line.tax_rate)) if line.tax_rate == int(line.tax_rate) else str(line.tax_rate)
        )
        exempt_code = _ksef_exempt_code(line.tax_category)
        row_lines = [
            "<FaWiersz>",
            f"  <NrWierszaFa>{xml_escape(line.line_id)}</NrWierszaFa>",
            f"  <P_7>{xml_escape(line.name)}</P_7>",
            f"  <P_8A>{xml_escape(line.unit_code or 'szt')}</P_8A>",
            f"  <P_8B>{format_amount(line.quantity)}</P_8B>",
            f"  <P_9A>{_d(line.unit_price)}</P_9A>",
            f"  <P_11>{_d(line.line_net_amount)}</P_11>",
            f"  <P_12>{xml_escape(rate_str)}</P_12>",
        ]
        if exempt_code:
            row_lines.append(f"  <P_12_XII>{xml_escape(exempt_code)}</P_12_XII>")
        row_lines.append("</FaWiersz>")
        rows.append("\n".join(row_lines))
    return "\n".join(rows)


def _fa3_podmiot3_block(entries: list[KSeFPodmiot3]) -> str:
    """Build one <Podmiot3> block per additional party entry."""
    parts: list[str] = []
    for p3 in entries:
        lines = ["<Podmiot3>", "  <DaneIdentyfikacyjne>"]
        if p3.nip:
            lines.append(f"    <NIP>{xml_escape(p3.nip)}</NIP>")
        lines.append(f"    <Nazwa>{xml_escape(p3.name)}</Nazwa>")
        lines.append("  </DaneIdentyfikacyjne>")
        lines.append(f"  <Rola>{xml_escape(p3.role_code)}</Rola>")
        if p3.role_description:
            lines.append(f"  <OpisRoli>{xml_escape(p3.role_description)}</OpisRoli>")
        lines.append("</Podmiot3>")
        parts.append("\n".join(lines))
    return "\n".join(parts)


def _fa3_podmiot_upowazniony_block(pu: KSeFPodmiotUpowazniony) -> str:
    """Build the <PodmiotUpowazniony> block."""
    return (
        "<PodmiotUpowazniony>\n"
        "  <DaneIdentyfikacyjne>\n"
        f"    <NIP>{xml_escape(pu.nip)}</NIP>\n"
        f"    <Nazwa>{xml_escape(pu.name)}</Nazwa>\n"
        "  </DaneIdentyfikacyjne>\n"
        "</PodmiotUpowazniony>"
    )


def _fa3_blok_danych(block: KSeFAttachment) -> str:
    """Build one <BlokDanych> element (ZNaglowek, MetaDane, Tekst, Tabela)."""
    lines: list[str] = ["<BlokDanych>"]
    if block.z_naglowek:
        lines.append(f"  <ZNaglowek>{xml_escape(block.z_naglowek)}</ZNaglowek>")
    for key, value in block.metadata:
        lines.append(
            f"  <MetaDane>\n"
            f"    <ZKlucz>{xml_escape(key)}</ZKlucz>\n"
            f"    <ZWartosc>{xml_escape(value)}</ZWartosc>\n"
            f"  </MetaDane>"
        )
    if block.text_paragraphs:
        lines.append("  <Tekst>")
        for paragraph in block.text_paragraphs:
            lines.append(f"    <Akapit>{xml_escape(paragraph)}</Akapit>")
        lines.append("  </Tekst>")
    lines.append("</BlokDanych>")
    return "\n".join(lines)


def _fa3_zalacznik_block(attachments: list[KSeFAttachment]) -> str:
    """Build a single <Zalacznik> element wrapping N <BlokDanych> children."""
    lines: list[str] = ["<Zalacznik>"]
    for block in attachments:
        for bl in _fa3_blok_danych(block).splitlines():
            lines.append(f"  {bl}")
    lines.append("</Zalacznik>")
    return "\n".join(lines)


def _fa3_correction_block(ref: KSeFCorrectionRef) -> str:
    """Build the <DaneFaKorygowanej> correction reference block.

    Verified against schemat_FA(3)_v1-0E.xsd: DataWystFaKorygowanej and
    NrFaKorygowanej are always emitted, followed by a choice of either
    (NrKSeF marker + NrKSeFFaKorygowanej value) or NrKSeFN (standalone marker).
    """
    lines: list[str] = [
        "<DaneFaKorygowanej>",
        f"  <DataWystFaKorygowanej>{xml_escape(str(ref.data_wyst))}</DataWystFaKorygowanej>",
        f"  <NrFaKorygowanej>{xml_escape(ref.nr_fa_korygowanej)}</NrFaKorygowanej>",
    ]
    if ref.numer_ksef:
        lines.append("  <NrKSeF>1</NrKSeF>")
        lines.append(
            f"  <NrKSeFFaKorygowanej>{xml_escape(ref.nr_ksef_fa_korygowanej)}</NrKSeFFaKorygowanej>"
        )
    else:
        lines.append("  <NrKSeFN>1</NrKSeFN>")
    lines.append("</DaneFaKorygowanej>")
    return "\n".join(lines)


def _fa3_platnosc_block(
    invoice: KSeFInvoice,
    ipksef: str = "",
    link_do_platnosci: str = "",
) -> str:
    """Build an optional <Platnosc> block when IBAN, due_date, or KSeF payment IDs are present.

    XSD <Platnosc> sequence (verified against schemat_FA(3)_v1-0E.xsd):
      Zaplacono-choice (not emitted here), TerminPlatnosci, FormaPlatnosci-choice,
      RachunekBankowy, RachunekBankowyFaktora, Skonto, LinkDoPlatnosci, IPKSeF.
    TerminPlatnosci only contains Termin/TerminOpis — FormaPlatnosci is a sibling
    element after TerminPlatnosci, not nested inside it.
    FormaPlatnosci=6 (przelew bankowy) is the standard default for B2B invoices.
    ipksef and link_do_platnosci are the KSeF-specific payment identifiers (PL-2.2).
    """
    pm = invoice.payment_means
    has_iban = pm and pm.iban
    has_due_date = invoice.due_date is not None
    if not has_iban and not has_due_date and not ipksef and not link_do_platnosci:
        return ""

    parts = ["<Platnosc>"]
    if has_due_date:
        parts.append(
            f"  <TerminPlatnosci>\n"
            f"    <Termin>{xml_escape(str(invoice.due_date))}</Termin>\n"
            f"  </TerminPlatnosci>"
        )
    parts.append("  <FormaPlatnosci>6</FormaPlatnosci>")
    if has_iban:
        parts.append(
            f"  <RachunekBankowy>\n    <NrRB>{xml_escape(pm.iban)}</NrRB>\n  </RachunekBankowy>"
        )
    if link_do_platnosci:
        parts.append(f"  <LinkDoPlatnosci>{xml_escape(link_do_platnosci)}</LinkDoPlatnosci>")
    if ipksef:
        parts.append(f"  <IPKSeF>{xml_escape(ipksef)}</IPKSeF>")
    parts.append("</Platnosc>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# FA(3) generator
# ---------------------------------------------------------------------------


class FA3Generator(BaseDocumentGenerator[KSeFInvoice]):
    """Generates KSeF FA(3) XML invoices for use with KSeF API v2.

    FA(3) is required for all new invoice submissions via KSeF API v2 online
    or batch sessions.  FA(2) is not accepted for new submissions.

    Schema: http://crd.gov.pl/wzor/2025/06/25/13775/
    XSD:    src/mcp_ksef_pl/schemas/schemat_FA(3)_v1-0E.xsd (bundled in the wheel;
            loaded via importlib.resources by FA3Validator)
    """

    def get_format_name(self) -> str:
        return "FA(3)"

    def get_country_code(self) -> str:
        return "PL"

    def get_namespace(self) -> str:
        return _NS3

    async def generate(  # noqa: C901
        self,
        invoice: KSeFInvoice,
        *,
        options: KSeFFA3Options | None = None,
    ) -> str:
        """Generate a KSeF-compliant FA(3) XML invoice.

        Args:
            invoice: Structured invoice data (KSeFInvoice).  seller.nip must be a
                     Polish NIP (10 digits).  buyer.nip may be a Polish NIP, or
                     eu_vat_country/eu_vat_id for EU cross-border, or neither (BrakID).
            options: Optional FA(3) extensions — correction reference, payment
                     identifiers, attachments, additional parties (PL-2.2/2.3/2.4/4.1).

        Returns:
            UTF-8 FA(3) XML string ready to be passed to submit_invoice_to_ksef.
        """
        opts = options or KSeFFA3Options()

        # PL-4.1: 50,000-line limit for collective correction invoices.
        if len(invoice.line_items) > 50_000:
            raise DocumentGenerationError(
                f"Invoice has {len(invoice.line_items)} lines; KSeF imposes a 50,000-line limit."
            )

        # PL-4.1: Correction invoices require a KSeF reference.
        rodzaj = opts.rodzaj_faktury.upper()
        if rodzaj in ("KOR", "KOR_ZAL", "KOR_ROZ") and not opts.correction:
            raise DocumentGenerationError(
                f"rodzaj_faktury={rodzaj} requires a correction reference "
                "(opts.correction must be set with the original invoice's numer_ksef)."
            )

        try:
            now_utc = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            vat_xml, p15_xml = _fa3_vat_fields(invoice.tax_lines or [])
            platnosc = _fa3_platnosc_block(
                invoice,
                ipksef=opts.ipksef,
                link_do_platnosci=opts.link_do_platnosci,
            )

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
            ]

            # PL-2.4: Additional parties (Podmiot3, PodmiotUpowazniony)
            if opts.podmiot3_entries:
                for bl in _fa3_podmiot3_block(opts.podmiot3_entries).splitlines():
                    parts.append(f"  {bl}")
            if opts.podmiot_upowazniony:
                for bl in _fa3_podmiot_upowazniony_block(opts.podmiot_upowazniony).splitlines():
                    parts.append(f"  {bl}")

            parts += [
                # --- Fa ---
                "  <Fa>",
                f"    <KodWaluty>{xml_escape(invoice.currency_code)}</KodWaluty>",
                f"    <P_1>{xml_escape(str(invoice.invoice_date))}</P_1>",
                f"    <P_2>{xml_escape(invoice.invoice_number)}</P_2>",
            ]

            # VAT rate bands (only non-zero bands are emitted)
            if vat_xml:
                for vl in vat_xml.splitlines():
                    parts.append(f"    {vl}")

            # Total gross (mandatory)
            parts.append(f"    {p15_xml}")

            # Adnotacje (mandatory, all defaults)
            for al in _adnotacje().splitlines():
                parts.append(f"    {al}")

            # RodzajFaktury (mandatory)
            parts.append(f"    <RodzajFaktury>{xml_escape(rodzaj)}</RodzajFaktury>")

            # PL-4.1: Correction reference block
            if opts.correction:
                for cl in _fa3_correction_block(opts.correction).splitlines():
                    parts.append(f"    {cl}")

            # Invoice lines (direct FaWiersz children, no wrapper)
            if invoice.line_items:
                for wl in _wiersz_lines(invoice).splitlines():
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

            # PL-2.3: Attachments — <Zalacznik> is the last Faktura-level child,
            # a sibling of <Fa>/<Stopka> emitted after <Stopka> (confirmed via
            # lxml parse of schemat_FA(3)_v1-0E.xsd: Faktura sequence is
            # Naglowek, Podmiot1, Podmiot2, Podmiot3?, PodmiotUpowazniony?, Fa,
            # Stopka?, Zalacznik?).
            if opts.attachments:
                for zl in _fa3_zalacznik_block(opts.attachments).splitlines():
                    parts.append(f"  {zl}")

            parts.append("</Faktura>")
            return "\n".join(parts) + "\n"

        except DocumentGenerationError:
            raise
        except Exception as exc:
            raise DocumentGenerationError(f"FA(3) generation failed: {exc}") from exc
