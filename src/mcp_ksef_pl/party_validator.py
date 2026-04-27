import re
from decimal import Decimal

from mcp_einvoicing_core import (
    BasePartyValidator,
    DocumentValidationResult,
    InvoiceParty,
    TaxIdentifier,
)

_NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
_REGON9_WEIGHTS = (8, 9, 2, 3, 4, 5, 6, 7)
_REGON14_WEIGHTS = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)


def validate_nip(nip: str) -> bool:
    """Return True when *nip* passes the Polish NIP checksum algorithm."""
    digits = re.sub(r"[\s\-]", "", nip)
    if not digits.isdigit() or len(digits) != 10:
        return False
    total = sum(int(d) * w for d, w in zip(digits, _NIP_WEIGHTS))
    remainder = total % 11
    return remainder != 10 and remainder == int(digits[9])


def validate_regon(regon: str) -> bool:
    """Return True when *regon* passes the 9- or 14-digit Polish REGON checksum."""
    digits = re.sub(r"\s", "", regon)
    if not digits.isdigit():
        return False
    if len(digits) == 9:
        total = sum(int(d) * w for d, w in zip(digits, _REGON9_WEIGHTS))
        return total % 11 % 10 == int(digits[8])
    if len(digits) == 14:
        total = sum(int(d) * w for d, w in zip(digits, _REGON14_WEIGHTS))
        return total % 11 % 10 == int(digits[13])
    return False


class PolishPartyValidator(BasePartyValidator):
    """Validates seller/buyer parties for KSeF compliance."""

    async def validate_tax_id(self, tax_id: TaxIdentifier) -> bool:
        if tax_id.country_code.upper() != "PL":
            # Non-Polish TIN — basic format check only
            return bool(tax_id.identifier)
        return validate_nip(tax_id.identifier)

    async def validate_seller(self, party: InvoiceParty) -> DocumentValidationResult:
        return await self._validate_ksef_party(party, "seller")

    async def validate_buyer(self, party: InvoiceParty) -> DocumentValidationResult:
        return await self._validate_ksef_party(party, "buyer")

    async def _validate_ksef_party(
        self, party: InvoiceParty, role: str
    ) -> DocumentValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        # NIP is mandatory for Polish sellers; warn for foreign buyers
        if party.tax_id.country_code.upper() == "PL":
            if not await self.validate_tax_id(party.tax_id):
                errors.append(
                    f"{role.capitalize()} NIP '{party.tax_id.identifier}' failed checksum validation."
                )
        else:
            warnings.append(
                f"{role.capitalize()} is non-Polish ({party.tax_id.country_code}); "
                "NIP checksum not applied."
            )

        if not party.address:
            errors.append(f"{role.capitalize()} address is required for KSeF.")
        elif not party.address.postal_code:
            warnings.append(f"{role.capitalize()} postal code is missing.")

        name = party.name or f"{party.first_name or ''} {party.last_name or ''}".strip()
        if not name:
            errors.append(f"{role.capitalize()} name is required.")

        return DocumentValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={"role": role, "nip": party.tax_id.identifier},
        )
