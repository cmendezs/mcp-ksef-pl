"""Tests for the FA(2) XML validator."""

import pytest
from mcp_einvoicing_core import InvoiceDocument

from mcp_ksef_pl.generator import FA2Generator
from mcp_ksef_pl.validator import FA2Validator

_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"


class TestFA2Validator:
    @pytest.fixture
    def validator(self) -> FA2Validator:
        return FA2Validator()

    @pytest.fixture
    def generator(self) -> FA2Generator:
        return FA2Generator()

    def test_schema_version(self, validator: FA2Validator) -> None:
        assert "FA(2)" in validator.get_schema_version()

    @pytest.mark.asyncio
    async def test_valid_xml_passes(
        self, validator: FA2Validator, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        result = await validator.validate(xml)
        assert result.valid, f"Expected valid, got errors: {result.errors}"

    @pytest.mark.asyncio
    async def test_missing_namespace_fails(self, validator: FA2Validator) -> None:
        bad_xml = "<Faktura><Fa><P_1>2024-01-01</P_1></Fa></Faktura>"
        result = await validator.validate(bad_xml)
        assert not result.valid
        assert any("namespace" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_seller_fails(self, validator: FA2Validator) -> None:
        xml = (
            f'<Faktura xmlns="{_NS}">'
            "<Naglowek>"
            '<KodFormularza kodSystemowy="FA (2)">FA</KodFormularza>'
            "<WariantFormularza>2</WariantFormularza>"
            "<DataWytworzenieFa>2024-01-01T00:00:00Z</DataWytworzenieFa>"
            "</Naglowek>"
            "<Podmiot2><DaneIdentyfikacyjne><NIP>5260250274</NIP></DaneIdentyfikacyjne></Podmiot2>"
            "<Fa><KodWaluty>PLN</KodWaluty><P_1>2024-01-01</P_1><P_2>001</P_2>"
            "<P_15>100.00</P_15><FaWiersze></FaWiersze>"
            "<Adnotacje><P_16>2</P_16><P_17>2</P_17><P_18>2</P_18>"
            "<P_18A>2</P_18A><P_23>2</P_23></Adnotacje></Fa>"
            "</Faktura>"
        )
        result = await validator.validate(xml)
        assert not result.valid
        assert any("Podmiot1" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_invoice_date_fails(self, validator: FA2Validator) -> None:
        xml = (
            f'<Faktura xmlns="{_NS}">'
            "<Naglowek>"
            '<KodFormularza kodSystemowy="FA (2)">FA</KodFormularza>'
            "<WariantFormularza>2</WariantFormularza>"
            "<DataWytworzenieFa>2024-01-01T00:00:00Z</DataWytworzenieFa>"
            "</Naglowek>"
            "<Podmiot1><DaneIdentyfikacyjne><NIP>5261040828</NIP></DaneIdentyfikacyjne></Podmiot1>"
            "<Podmiot2><DaneIdentyfikacyjne><NIP>5260250274</NIP></DaneIdentyfikacyjne></Podmiot2>"
            "<Fa><KodWaluty>PLN</KodWaluty><P_2>001</P_2>"
            "<P_15>100.00</P_15><FaWiersze></FaWiersze></Fa>"
            "</Faktura>"
        )
        result = await validator.validate(xml)
        assert not result.valid
        assert any("P_1" in e for e in result.errors)
