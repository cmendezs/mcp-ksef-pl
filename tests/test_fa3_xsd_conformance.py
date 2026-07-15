"""Generate -> FA3Validator XSD roundtrip tests.

These are the guardrail that would have caught PL-2.6/2.7/4.2 pre-release:
each fixture below reproduces the shape of invoice that previously produced
XSD-invalid XML. Skips cleanly if lxml is missing (it is a required
dependency, but the skip keeps this test file portable).
"""

from datetime import date

import pytest
from mcp_einvoicing_core.en16931 import EN16931PaymentMeans

from mcp_ksef_pl.generator import FA3Generator
from mcp_ksef_pl.models import (
    KSeFAttachment,
    KSeFCorrectionRef,
    KSeFFA3Options,
    KSeFInvoice,
)
from mcp_ksef_pl.validator import FA3Validator

try:
    import lxml  # noqa: F401

    _HAS_LXML = True
except ImportError:
    _HAS_LXML = False

pytestmark = pytest.mark.skipif(not _HAS_LXML, reason="lxml not installed")


@pytest.fixture
def generator() -> FA3Generator:
    return FA3Generator()


@pytest.fixture
def validator() -> FA3Validator:
    return FA3Validator()


class TestFA3XSDConformance:
    @pytest.mark.asyncio
    async def test_vanilla_invoice_is_xsd_valid(
        self, generator: FA3Generator, validator: FA3Validator, sample_invoice: KSeFInvoice
    ) -> None:
        xml = await generator.generate(sample_invoice)
        result = await validator.validate(xml)
        assert result.metadata.get("xsd_validated") is True, result.warnings
        assert result.valid is True, result.errors

    @pytest.mark.asyncio
    async def test_payment_block_is_xsd_valid(
        self, generator: FA3Generator, validator: FA3Validator, sample_invoice: KSeFInvoice
    ) -> None:
        invoice = sample_invoice.model_copy(
            update={
                "due_date": date(2024, 4, 15),
                "payment_means": EN16931PaymentMeans(
                    type_code="58", iban="PL61109010140000071219812874"
                ),
            }
        )
        options = KSeFFA3Options(
            ipksef="001AB12345678",
            link_do_platnosci="https://platnosc.ksef.mf.gov.pl/pay?IPKSeF=001AB12345678",
        )
        xml = await generator.generate(invoice, options=options)
        result = await validator.validate(xml)
        assert result.metadata.get("xsd_validated") is True, result.warnings
        assert result.valid is True, result.errors

    @pytest.mark.asyncio
    async def test_correction_invoice_ksef_branch_is_xsd_valid(
        self, generator: FA3Generator, validator: FA3Validator, sample_invoice: KSeFInvoice
    ) -> None:
        options = KSeFFA3Options(
            rodzaj_faktury="KOR",
            correction=KSeFCorrectionRef(
                data_wyst=date(2024, 1, 10),
                nr_fa_korygowanej="FV/2024/000",
                numer_ksef=True,
                nr_ksef_fa_korygowanej="5261040828-20240110-ABCDEF012345-CD",
            ),
        )
        xml = await generator.generate(sample_invoice, options=options)
        result = await validator.validate(xml)
        assert result.metadata.get("xsd_validated") is True, result.warnings
        assert result.valid is True, result.errors

    @pytest.mark.asyncio
    async def test_correction_invoice_ksefn_branch_is_xsd_valid(
        self, generator: FA3Generator, validator: FA3Validator, sample_invoice: KSeFInvoice
    ) -> None:
        options = KSeFFA3Options(
            rodzaj_faktury="KOR",
            correction=KSeFCorrectionRef(
                data_wyst=date(2024, 1, 10),
                nr_fa_korygowanej="FV/2024/000",
                numer_ksefn=True,
            ),
        )
        xml = await generator.generate(sample_invoice, options=options)
        result = await validator.validate(xml)
        assert result.metadata.get("xsd_validated") is True, result.warnings
        assert result.valid is True, result.errors

    @pytest.mark.asyncio
    async def test_attachment_block_is_xsd_valid(
        self, generator: FA3Generator, validator: FA3Validator, sample_invoice: KSeFInvoice
    ) -> None:
        options = KSeFFA3Options(
            attachments=[
                KSeFAttachment(
                    z_naglowek="Zestawienie dostaw",
                    metadata=[("okres", "2024-03"), ("liczba_pozycji", "12")],
                    text_paragraphs=["Szczegółowe zestawienie w załączeniu."],
                )
            ]
        )
        xml = await generator.generate(sample_invoice, options=options)
        result = await validator.validate(xml)
        assert result.metadata.get("xsd_validated") is True, result.warnings
        assert result.valid is True, result.errors
        assert xml.index("</Fa>") < xml.index("<Zalacznik>")
