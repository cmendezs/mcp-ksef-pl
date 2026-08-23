"""Tests for PeppolValidator (CORE-EN16931-BASE-SCHEMATRON-1)."""

from __future__ import annotations

import importlib.util

import pytest

from mcp_ksef_pl.models import KSeFInvoice
from mcp_ksef_pl.peppol import PeppolUBLGenerator
from mcp_ksef_pl.peppol.validator import PeppolValidator

_SAXON_AVAILABLE = importlib.util.find_spec("saxonche") is not None

pytestmark = pytest.mark.skipif(not _SAXON_AVAILABLE, reason="saxonche extra not installed")


class TestPeppolValidator:
    @pytest.fixture
    def validator(self) -> PeppolValidator:
        return PeppolValidator()

    def test_schema_version(self, validator: PeppolValidator) -> None:
        assert "EN16931" in validator.get_schema_version()

    @pytest.mark.asyncio
    async def test_malformed_xml_reports_xml_parse_error(self, validator: PeppolValidator) -> None:
        result = await validator.validate("<not valid xml")
        assert result.valid is False
        assert result.metadata["engine"] == "schematron-xslt"
        assert result.metadata["scope"] == "en16931-base-only"
        assert any("XML-PARSE" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_generate_validate_roundtrip_scope_and_metadata(
        self, validator: PeppolValidator, sample_invoice: KSeFInvoice
    ) -> None:
        """Real CEN EN16931 base validation now runs (was: no validator at
        all for this package's Peppol path). Result always carries an
        explicit en16931-base-only scope warning regardless of pass/fail."""
        generator = PeppolUBLGenerator()
        xml = await generator.generate(sample_invoice)
        result = await validator.validate(xml)
        assert result.metadata["engine"] == "schematron-xslt"
        assert result.metadata["scope"] == "en16931-base-only"
        assert any("EN16931-BASE-ONLY-SCOPE" in w for w in result.warnings)
