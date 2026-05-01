"""Tests for Polish NIP and REGON validation."""

import pytest
from mcp_einvoicing_core import InvoiceParty, TaxIdentifier

from mcp_ksef_pl.party_validator import PolishPartyValidator, validate_nip, validate_regon


class TestNIP:
    @pytest.mark.parametrize(
        "nip,expected",
        [
            ("5261040828", True),   # Ministerstwo Finansów — real NIP, checksum verified
            ("5260250274", True),   # valid NIP
            ("1234567890", False),  # weighted sum mod 11 == 10 → structurally impossible
            ("000000000", False),   # too short (9 digits)
            ("abcdefghij", False),  # non-digits
            ("526-104-08-28", True),  # dashes are stripped before validation
            ("526 104 08 28", True),  # spaces are stripped before validation
            ("5261040827", False),  # off-by-one from valid MF NIP — checksum fails
        ],
    )
    def test_validate_nip(self, nip: str, expected: bool) -> None:
        assert validate_nip(nip) == expected


class TestREGON:
    @pytest.mark.parametrize(
        "regon,expected",
        [
            ("000331501", True),         # GUS (Central Statistical Office) — verified
            ("000331502", False),        # off-by-one check digit — checksum fails
            ("00033150100017", True),    # valid 14-digit REGON (GUS + local unit)
            ("00033150100018", False),   # off-by-one 14-digit — checksum fails
            ("abc", False),              # non-digits
        ],
    )
    def test_validate_regon(self, regon: str, expected: bool) -> None:
        assert validate_regon(regon) == expected


class TestPolishPartyValidator:
    @pytest.fixture
    def validator(self) -> PolishPartyValidator:
        return PolishPartyValidator()

    @pytest.mark.asyncio
    async def test_valid_seller(
        self, validator: PolishPartyValidator, polish_seller: InvoiceParty
    ) -> None:
        result = await validator.validate_seller(polish_seller)
        assert result.valid
        assert not result.errors

    @pytest.mark.asyncio
    async def test_invalid_nip(self, validator: PolishPartyValidator) -> None:
        party = InvoiceParty(
            tax_id=TaxIdentifier(country_code="PL", identifier="1234567890"),
            name="Test Firma",
        )
        result = await validator.validate_seller(party)
        assert not result.valid
        assert any("NIP" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_tax_id_non_polish(self, validator: PolishPartyValidator) -> None:
        from mcp_einvoicing_core import PartyAddress

        party = InvoiceParty(
            tax_id=TaxIdentifier(country_code="DE", identifier="DE123456789"),
            name="German GmbH",
            address=PartyAddress(
                street="Unter den Linden 1",
                postal_code="10117",
                city="Berlin",
                country_code="DE",
            ),
        )
        result = await validator.validate_buyer(party)
        # Non-Polish party: NIP checksum is skipped, should pass with a warning
        assert result.valid, f"Expected valid, got errors: {result.errors}"
        assert any("non-Polish" in w for w in result.warnings)
