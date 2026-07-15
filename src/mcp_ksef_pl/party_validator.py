from mcp_einvoicing_core import (
    BasePartyValidator,
    DocumentValidationResult,
    TaxIdentifier,
)


def validate_nip(nip: str) -> bool:
    """Return True when *nip* passes the Polish NIP checksum algorithm."""
    return TaxIdentifier.validate_pl_nip(nip)[0]


def validate_regon(regon: str) -> bool:
    """Return True when *regon* passes the 9- or 14-digit Polish REGON checksum."""
    return TaxIdentifier.validate_pl_regon(regon)[0]


def _extract_nip_and_country(party: object) -> tuple[str, str]:
    """Extract (nip, country_code) from either a KSeFParty or an InvoiceParty.

    KSeFParty has `.nip` and optional `.eu_vat_country`.
    InvoiceParty has `.tax_id.identifier` and `.tax_id.country_code`.
    Returns ("", "PL") when no identifier is found.
    """
    # KSeFParty path
    if hasattr(party, "nip"):
        nip = party.nip or ""
        country = "PL" if nip else (party.eu_vat_country or "PL")
        return nip, country.upper()
    # InvoiceParty path
    tax_id = getattr(party, "tax_id", None)
    if tax_id is not None:
        return tax_id.identifier or "", tax_id.country_code.upper()
    return "", "PL"


def _extract_address_postcode(party: object) -> tuple[bool, str | None]:
    """Return (has_address, postal_code_or_none) for either party type."""
    addr = getattr(party, "address", None)
    if addr is None:
        return False, None
    # EN16931Address uses .postcode; PartyAddress uses .postal_code
    postcode = getattr(addr, "postcode", None) or getattr(addr, "postal_code", None)
    return True, postcode


class PolishPartyValidator(BasePartyValidator):
    """Validates seller/buyer parties for KSeF compliance.

    Accepts both KSeFParty (EN16931-based, with .nip field) and legacy
    InvoiceParty (with .tax_id) so that server-level tools and tests can
    pass either type without type errors.
    """

    async def validate_tax_id(self, tax_id: TaxIdentifier) -> bool:
        if tax_id.country_code.upper() != "PL":
            # Non-Polish TIN — basic format check only
            return bool(tax_id.identifier)
        return validate_nip(tax_id.identifier)

    async def validate_seller(self, party: object) -> DocumentValidationResult:
        return await self._validate_ksef_party(party, "seller")

    async def validate_buyer(self, party: object) -> DocumentValidationResult:
        return await self._validate_ksef_party(party, "buyer")

    async def _validate_ksef_party(
        self, party: object, role: str
    ) -> DocumentValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        nip, country = _extract_nip_and_country(party)

        # NIP is mandatory for Polish sellers; warn for foreign buyers
        if country == "PL":
            if not validate_nip(nip):
                errors.append(
                    f"{role.capitalize()} NIP '{nip}'"
                    " failed checksum validation."
                )
        else:
            warnings.append(
                f"{role.capitalize()} is non-Polish ({country}); "
                "NIP checksum not applied."
            )

        has_address, postcode = _extract_address_postcode(party)
        if not has_address:
            errors.append(f"{role.capitalize()} address is required for KSeF.")
        elif not postcode:
            warnings.append(f"{role.capitalize()} postal code is missing.")

        name = getattr(party, "name", "") or ""
        if not name:
            first = getattr(party, "first_name", "") or ""
            last = getattr(party, "last_name", "") or ""
            name = f"{first} {last}".strip()
        if not name:
            errors.append(f"{role.capitalize()} name is required.")

        return DocumentValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={"role": role, "nip": nip},
        )
