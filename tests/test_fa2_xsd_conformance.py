"""Generate -> FA2Validator XSD roundtrip tests.

PL-PAY-1 guardrail: a payment-bearing FA(2) invoice (due_date + IBAN) previously
generated XSD-invalid XML (a non-existent <P_6> due-date field and an unwrapped
<RachunekBankowy>). `sample_invoice` alone does not exercise this path since it
has neither due_date nor payment_means, so this fixture adds both. Skips
cleanly if lxml is missing (it is a required dependency, but the skip keeps
this test file portable).
"""

from datetime import date

import pytest
from mcp_einvoicing_core.en16931 import EN16931PaymentMeans

from mcp_ksef_pl.generator import FA2Generator
from mcp_ksef_pl.models import KSeFInvoice
from mcp_ksef_pl.validator import FA2Validator

try:
    import lxml  # noqa: F401

    _HAS_LXML = True
except ImportError:
    _HAS_LXML = False

pytestmark = pytest.mark.skipif(not _HAS_LXML, reason="lxml not installed")


@pytest.fixture
def generator() -> FA2Generator:
    return FA2Generator()


@pytest.fixture
def validator() -> FA2Validator:
    return FA2Validator()


class TestFA2XSDConformance:
    @pytest.mark.asyncio
    async def test_vanilla_invoice_is_xsd_valid(
        self, generator: FA2Generator, validator: FA2Validator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        result = await validator.validate(xml)
        assert result.metadata.get("xsd_validated") is True, result.warnings
        assert result.valid is True, result.errors

    @pytest.mark.asyncio
    async def test_payment_block_is_xsd_valid(
        self, generator: FA2Generator, validator: FA2Validator, sample_invoice: KSeFInvoice
    ) -> None:
        invoice = sample_invoice.model_copy(
            update={
                "due_date": date(2024, 4, 15),
                "payment_means": EN16931PaymentMeans(
                    type_code="58", iban="PL61109010140000071219812874"
                ),
            }
        )
        xml = await generator.generate(invoice)
        result = await validator.validate(xml)
        assert result.metadata.get("xsd_validated") is True, result.warnings
        assert result.valid is True, result.errors

    @pytest.mark.asyncio
    async def test_due_date_only_is_xsd_valid(
        self, generator: FA2Generator, validator: FA2Validator, sample_invoice: KSeFInvoice
    ) -> None:
        invoice = sample_invoice.model_copy(update={"due_date": date(2024, 4, 15)})
        xml = await generator.generate(invoice)
        result = await validator.validate(xml)
        assert result.metadata.get("xsd_validated") is True, result.warnings
        assert result.valid is True, result.errors
