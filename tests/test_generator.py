"""Tests for the FA(2) XML generator."""

import pytest
from mcp_einvoicing_core import InvoiceDocument

from mcp_ksef_pl.generator import FA2Generator

_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"


class TestFA2Generator:
    @pytest.fixture
    def generator(self) -> FA2Generator:
        return FA2Generator()

    def test_format_metadata(self, generator: FA2Generator) -> None:
        assert generator.get_format_name() == "FA(2)"
        assert generator.get_country_code() == "PL"
        assert generator.get_namespace() == _NS

    @pytest.mark.asyncio
    async def test_generate_contains_namespace(
        self, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert _NS in xml

    @pytest.mark.asyncio
    async def test_generate_header_fields(
        self, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<KodFormularza" in xml
        assert "FA (2)" in xml
        assert "<WariantFormularza>2</WariantFormularza>" in xml
        assert "<DataWytworzenieFa>" in xml

    @pytest.mark.asyncio
    async def test_generate_seller_nip(
        self, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Podmiot1>" in xml
        assert "<NIP>5261040828</NIP>" in xml

    @pytest.mark.asyncio
    async def test_generate_buyer(
        self, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<Podmiot2>" in xml

    @pytest.mark.asyncio
    async def test_generate_invoice_fields(
        self, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<P_1>2024-03-15</P_1>" in xml
        assert "<P_2>FV/2024/001</P_2>" in xml
        assert "<KodWaluty>PLN</KodWaluty>" in xml

    @pytest.mark.asyncio
    async def test_generate_vat_fields(
        self, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        # 23% VAT → P_13_1, P_14_1
        assert "<P_13_1>2000.00</P_13_1>" in xml
        assert "<P_14_1>460.00</P_14_1>" in xml
        assert "<P_15>2460.00</P_15>" in xml

    @pytest.mark.asyncio
    async def test_generate_invoice_lines(
        self, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<FaWiersze>" in xml
        assert "<FaWiersz>" in xml
        assert "<P_7>Usługi konsultingowe</P_7>" in xml

    @pytest.mark.asyncio
    async def test_generate_note(
        self, generator: FA2Generator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<StopkaFaktury>" in xml
        assert "Termin płatności" in xml
