"""Tests for Polish NIP and REGON validation."""

import pytest
from mcp_einvoicing_core import InvoiceParty, TaxIdentifier

from mcp_ksef_pl.party_validator import PolishPartyValidator, validate_nip, validate_regon


class TestNIP:
    @pytest.mark.parametrize(
        "nip,expected",
        [
            ("5261040828", True),   # Ministerstwo Finansów
            ("5260250274", True),   # valid NIP
            ("1234567890", False),  # invalid checksum
            ("000000000", False),   # too short
            ("abcdefghij", False),  # non-digits
            ("526-104-08-28", True),  # dashes allowed
            ("526 104 08 28", True),  # spaces allowed
            ("9999999999", False),  # checksum mod 11 == 10 → invalid
        ],
    )
    def test_validate_nip(self, nip: str, expected: bool) -> None:
        assert validate_nip(nip) == expected


class TestREGON:
    @pytest.mark.parametrize(
        "regon,expected",
        [
            ("180715408", True),   # valid 9-digit REGON
            ("123456785", False),  # invalid checksum
            ("00000000000000", False),  # all zeros — invalid checksum
            ("abc", False),        # non-digits
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
        party = InvoiceParty(
            tax_id=TaxIdentifier(country_code="DE", identifier="DE123456789"),
            name="German GmbH",
        )
        result = await validator.validate_buyer(party)
        # Non-Polish: no NIP check, just warnings
        assert result.valid
        assert any("non-Polish" in w for w in result.warnings)
