"""Tests for the Peppol BIS 3.0 / EN 16931 UBL generator."""

import pytest
from mcp_einvoicing_core import InvoiceDocument

from mcp_ksef_pl.peppol import PeppolUBLGenerator

_CUSTOMIZATION = "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
_PROFILE = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"


class TestPeppolUBLGenerator:
    @pytest.fixture
    def generator(self) -> PeppolUBLGenerator:
        return PeppolUBLGenerator()

    def test_format_metadata(self, generator: PeppolUBLGenerator) -> None:
        assert generator.get_format_name() == "Peppol-BIS-3.0-UBL"
        assert generator.get_country_code() == "PL"

    @pytest.mark.asyncio
    async def test_generate_contains_customization(
        self, generator: PeppolUBLGenerator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert _CUSTOMIZATION in xml
        assert _PROFILE in xml

    @pytest.mark.asyncio
    async def test_generate_invoice_id_and_date(
        self, generator: PeppolUBLGenerator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<cbc:ID>FV/2024/001</cbc:ID>" in xml
        assert "<cbc:IssueDate>2024-03-15</cbc:IssueDate>" in xml

    @pytest.mark.asyncio
    async def test_generate_currency(
        self, generator: PeppolUBLGenerator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<cbc:DocumentCurrencyCode>PLN</cbc:DocumentCurrencyCode>" in xml

    @pytest.mark.asyncio
    async def test_generate_supplier_and_customer(
        self, generator: PeppolUBLGenerator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<cac:AccountingSupplierParty>" in xml
        assert "<cac:AccountingCustomerParty>" in xml

    @pytest.mark.asyncio
    async def test_generate_tax_total(
        self, generator: PeppolUBLGenerator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<cac:TaxTotal>" in xml
        assert 'currencyID="PLN"' in xml

    @pytest.mark.asyncio
    async def test_generate_monetary_total(
        self, generator: PeppolUBLGenerator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<cac:LegalMonetaryTotal>" in xml
        assert "<cbc:PayableAmount" in xml

    @pytest.mark.asyncio
    async def test_generate_invoice_lines(
        self, generator: PeppolUBLGenerator, sample_invoice: InvoiceDocument
    ) -> None:
        xml = await generator.generate(sample_invoice)
        assert "<cac:InvoiceLine>" in xml
        assert "Usługi konsultingowe" in xml
