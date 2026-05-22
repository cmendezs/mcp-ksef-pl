"""Shared fixtures for mcp-ksef-pl tests."""

from datetime import date
from decimal import Decimal

import pytest
from mcp_einvoicing_core.en16931 import EN16931Address, EN16931LineItem, EN16931Tax

from mcp_ksef_pl.models import KSeFInvoice, KSeFParty


@pytest.fixture
def polish_seller() -> KSeFParty:
    return KSeFParty(
        name="Ministerstwo Finansów",
        nip="5261040828",
        address=EN16931Address(
            line_one="ul. Świętokrzyska 12",
            city="Warszawa",
            postcode="00-916",
            country_code="PL",
        ),
    )


@pytest.fixture
def polish_buyer() -> KSeFParty:
    return KSeFParty(
        name="Przykładowy Nabywca Sp. z o.o.",
        nip="5260250274",
        address=EN16931Address(
            line_one="ul. Marszałkowska 1",
            city="Warszawa",
            postcode="00-001",
            country_code="PL",
        ),
    )


@pytest.fixture
def sample_invoice(polish_seller: KSeFParty, polish_buyer: KSeFParty) -> KSeFInvoice:
    return KSeFInvoice(
        profile="KSeF",
        invoice_number="FV/2024/001",
        invoice_date=date(2024, 3, 15),
        invoice_type_code="INVOICE",
        currency_code="PLN",
        seller=polish_seller,
        buyer=polish_buyer,
        sum_of_line_net_amounts=Decimal("2000.00"),
        tax_exclusive_amount=Decimal("2000.00"),
        tax_total=Decimal("460.00"),
        tax_inclusive_amount=Decimal("2460.00"),
        amount_due=Decimal("2460.00"),
        tax_lines=[
            EN16931Tax(
                category="S",
                rate=Decimal("23"),
                taxable_amount=Decimal("2000.00"),
                tax_amount=Decimal("460.00"),
            ),
        ],
        line_items=[
            EN16931LineItem(
                line_id="1",
                name="Usługi konsultingowe",
                quantity=Decimal("10"),
                unit_code="godz",
                unit_price=Decimal("200.00"),
                line_net_amount=Decimal("2000.00"),
                tax_category="S",
                tax_rate=Decimal("23"),
            )
        ],
        note="Termin płatności: 14 dni",
    )
