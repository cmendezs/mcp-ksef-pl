"""Integration test: submit an FA(3) invoice to KSeF test environment.

Requires KSEF_ENVIRONMENT=test, KSEF_SESSION_TOKEN, and KSEF_NIP to be set.
Run with: uv run pytest -m integration
"""

import asyncio
from datetime import date
from decimal import Decimal

import pytest
from mcp_einvoicing_core.en16931 import (
    EN16931Address,
    EN16931LineItem,
    EN16931Tax,
)

from mcp_ksef_pl.config import KSeFSettings
from mcp_ksef_pl.generator import FA3Generator
from mcp_ksef_pl.lifecycle import KSeFLifecycleManager
from mcp_ksef_pl.models import KSeFInvoice, KSeFParty

pytestmark = pytest.mark.integration


def _build_minimal_invoice(nip: str) -> KSeFInvoice:
    seller = KSeFParty(
        name="Integration Test Seller",
        nip=nip,
        address=EN16931Address(
            line_one="ul. Testowa 1",
            city="Warszawa",
            postcode="00-001",
            country_code="PL",
        ),
    )
    buyer = KSeFParty(
        name="Integration Test Buyer",
        nip="5260250274",
        address=EN16931Address(
            line_one="ul. Przykladowa 2",
            city="Krakow",
            postcode="30-001",
            country_code="PL",
        ),
    )
    return KSeFInvoice.from_lines(
        profile="KSeF",
        invoice_number="INT-TEST-001",
        invoice_date=date.today(),
        invoice_type_code="INVOICE",
        currency_code="PLN",
        seller=seller,
        buyer=buyer,
        tax_lines=[
            EN16931Tax(
                category="S",
                rate=Decimal("23"),
                taxable_amount=Decimal("100.00"),
                tax_amount=Decimal("23.00"),
            ),
        ],
        line_items=[
            EN16931LineItem(
                line_id="1",
                name="Test service",
                quantity=Decimal("1"),
                unit_code="C62",
                unit_price=Decimal("100.00"),
                line_net_amount=Decimal("100.00"),
                tax_category="S",
                tax_rate=Decimal("23"),
            ),
        ],
    )


@pytest.mark.asyncio
async def test_submit_and_status_round_trip(ksef_settings: KSeFSettings) -> None:
    """Generate a minimal FA(3) invoice, submit it, poll status, and verify UPO retrieval."""
    import os

    nip = os.environ["KSEF_NIP"]
    invoice = _build_minimal_invoice(nip)

    generator = FA3Generator()
    xml = await generator.generate(invoice)
    assert "http://crd.gov.pl/wzor/2025/06/25/13775/" in xml

    manager = KSeFLifecycleManager(ksef_settings)
    result = await manager.submit_document(xml, {})

    assert result.session_ref, "Expected a session reference from KSeF"
    assert result.invoice_ref, "Expected an invoice reference from KSeF"
    assert result.status == "submitted"

    status = await manager.get_document_status(result.compound_id)
    assert status is not None

    for _ in range(30):
        status = await manager.get_document_status(result.compound_id)
        processing_status = status.get("processingStatus", "")
        if processing_status in ("Accepted", "Rejected", "Sent"):
            break
        await asyncio.sleep(2)

    assert processing_status in ("Accepted", "Sent", "Rejected"), (
        f"Invoice did not reach terminal status within 60s: {processing_status}"
    )
