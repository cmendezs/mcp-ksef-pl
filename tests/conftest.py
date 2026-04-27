"""Shared fixtures for mcp-ksef-pl tests."""

from decimal import Decimal

import pytest
from mcp_einvoicing_core import (
    InvoiceDocument,
    InvoiceLineItem,
    InvoiceParty,
    PartyAddress,
    TaxIdentifier,
    VATSummary,
)


@pytest.fixture
def polish_seller() -> InvoiceParty:
    return InvoiceParty(
        tax_id=TaxIdentifier(country_code="PL", identifier="5261040828"),  # MF NIP
        name="Ministerstwo Finansów",
        address=PartyAddress(
            street="ul. Świętokrzyska 12",
            postal_code="00-916",
            city="Warszawa",
            country_code="PL",
        ),
    )


@pytest.fixture
def polish_buyer() -> InvoiceParty:
    return InvoiceParty(
        tax_id=TaxIdentifier(country_code="PL", identifier="5260250274"),
        name="Przykładowy Nabywca Sp. z o.o.",
        address=PartyAddress(
            street="ul. Marszałkowska 1",
            postal_code="00-001",
            city="Warszawa",
            country_code="PL",
        ),
    )


@pytest.fixture
def sample_invoice(polish_seller: InvoiceParty, polish_buyer: InvoiceParty) -> InvoiceDocument:
    return InvoiceDocument(
        document_type="INVOICE",
        date="2024-03-15",
        number="FV/2024/001",
        currency="PLN",
        transmission_format="KSeF-FA2",
        seller=polish_seller,
        buyer=polish_buyer,
        lines=[
            InvoiceLineItem(
                line_number=1,
                description="Usługi konsultingowe",
                quantity=Decimal("10"),
                unit_of_measure="godz",
                unit_price=Decimal("200.00"),
                total_price=Decimal("2000.00"),
                vat_rate=Decimal("23"),
                currency="PLN",
            ),
        ],
        vat_summary=[
            VATSummary(
                vat_rate=Decimal("23"),
                taxable_base=Decimal("2000.00"),
                vat_amount=Decimal("460.00"),
            )
        ],
        note="Termin płatności: 14 dni",
    )
