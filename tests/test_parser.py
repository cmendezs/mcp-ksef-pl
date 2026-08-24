"""Tests for the FA(2) XML parser."""

from datetime import date
from decimal import Decimal

import pytest

from mcp_ksef_pl.generator import FA2Generator
from mcp_ksef_pl.models import KSeFInvoice, KSeFParty
from mcp_ksef_pl.parser import FA2Parser

_RAW_FA2_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2023/06/29/12648/">
  <Naglowek>
    <KodFormularza kodSystemowy="FA (2)" wersjaSchemy="1-0E">FA</KodFormularza>
    <DataWytworzenieFa>2024-03-15T10:00:00Z</DataWytworzenieFa>
    <SystemInfo>mcp-ksef-pl</SystemInfo>
  </Naglowek>
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>5261040828</NIP>
      <Nazwa>Ministerstwo Finansow</Nazwa>
    </DaneIdentyfikacyjne>
    <Adres>
      <KodKraju>PL</KodKraju>
      <AdresL1>ul. Swietokrzyska 12</AdresL1>
    </Adres>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>5260250274</NIP>
      <Nazwa>Przykladowy Nabywca</Nazwa>
    </DaneIdentyfikacyjne>
    <Adres>
      <KodKraju>PL</KodKraju>
      <AdresL1>ul. Marszalkowska 1</AdresL1>
    </Adres>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2024-03-15</P_1>
    <P_2>FV/2024/001</P_2>
    <P_6>2024-03-10</P_6>
    <P_13_1>2000.00</P_13_1>
    <P_14_1>460.00</P_14_1>
    <P_15>2460.00</P_15>
    <FaWiersz>
      <NrWierszaFa>1</NrWierszaFa>
      <P_7>Uslugi konsultingowe</P_7>
      <P_8A>godz</P_8A>
      <P_8B>10</P_8B>
      <P_9A>200.00</P_9A>
      <P_11>2000.00</P_11>
      <P_12>23</P_12>
    </FaWiersz>
    <FaWiersz>
      <NrWierszaFa>2</NrWierszaFa>
      <P_7>Materialy</P_7>
      <P_8A>szt</P_8A>
      <P_8B>5</P_8B>
      <P_9A>100.00</P_9A>
      <P_11>500.00</P_11>
      <P_12>23</P_12>
    </FaWiersz>
    <Platnosc>
      <TerminPlatnosci>
        <Termin>2024-03-29</Termin>
      </TerminPlatnosci>
      <FormaPlatnosci>6</FormaPlatnosci>
    </Platnosc>
  </Fa>
</Faktura>
"""


@pytest.fixture
def parser() -> FA2Parser:
    return FA2Parser()


class TestFA2ParserRawXml:
    @pytest.mark.asyncio
    async def test_lines_parsed_without_wrapper(self, parser: FA2Parser) -> None:
        data = await parser.parse(_RAW_FA2_XML)
        assert len(data["lines"]) == 2
        assert data["lines"][0]["description"] == "Uslugi konsultingowe"
        assert data["lines"][1]["description"] == "Materialy"

    @pytest.mark.asyncio
    async def test_due_date_reads_platnosc_termin(self, parser: FA2Parser) -> None:
        data = await parser.parse(_RAW_FA2_XML)
        assert data["invoice"]["due_date"] == "2024-03-29"

    @pytest.mark.asyncio
    async def test_supply_date_reads_p6_separately(self, parser: FA2Parser) -> None:
        data = await parser.parse(_RAW_FA2_XML)
        assert data["invoice"]["supply_date"] == "2024-03-10"
        assert data["invoice"]["supply_date"] != data["invoice"]["due_date"]

    @pytest.mark.asyncio
    async def test_to_invoice_document_includes_lines(self, parser: FA2Parser) -> None:
        doc = await parser.to_invoice_document(_RAW_FA2_XML)
        assert len(doc.lines) == 2
        assert doc.lines[0].description == "Uslugi konsultingowe"
        assert doc.lines[0].total_price == Decimal("2000.00")
        assert doc.lines[1].total_price == Decimal("500.00")


class TestFA2ParserRoundTrip:
    @pytest.mark.asyncio
    async def test_generator_output_parses_back(
        self, polish_seller: KSeFParty, polish_buyer: KSeFParty
    ) -> None:
        from mcp_einvoicing_core.en16931 import EN16931LineItem, EN16931Tax

        invoice = KSeFInvoice(
            profile="KSeF",
            invoice_number="FV/2024/002",
            invoice_date=date(2024, 3, 15),
            due_date=date(2024, 3, 29),
            invoice_type_code="INVOICE",
            currency_code="PLN",
            seller=polish_seller,
            buyer=polish_buyer,
            sum_of_line_net_amounts=Decimal("2000.00"),
            tax_exclusive_amount=Decimal("2000.00"),
            tax_total=Decimal("460.00"),
            tax_inclusive_amount=Decimal("2460.00"),
            amount_due=Decimal("2460.00"),
            tax_lines=[
                EN16931Tax(
                    category="S",
                    rate=Decimal("23"),
                    taxable_amount=Decimal("2000.00"),
                    tax_amount=Decimal("460.00"),
                ),
            ],
            line_items=[
                EN16931LineItem(
                    line_id="1",
                    name="Uslugi konsultingowe",
                    quantity=Decimal("10"),
                    unit_code="godz",
                    unit_price=Decimal("200.00"),
                    line_net_amount=Decimal("2000.00"),
                    tax_category="S",
                    tax_rate=Decimal("23"),
                )
            ],
        )

        xml = await FA2Generator().generate(invoice)
        data = await FA2Parser().parse(xml)

        assert len(data["lines"]) == 1
        assert data["lines"][0]["description"] == "Uslugi konsultingowe"
        assert data["invoice"]["due_date"] == "2024-03-29"
