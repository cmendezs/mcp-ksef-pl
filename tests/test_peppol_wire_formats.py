"""Tests for KSeFPeppolUBLSerializer and KSeFPeppolUBLParser (PL-CORE-1)."""

from datetime import date
from decimal import Decimal

import pytest
from mcp_einvoicing_core.en16931 import EN16931Address, EN16931LineItem, EN16931Tax

from mcp_ksef_pl.models import KSeFInvoice, KSeFParty
from mcp_ksef_pl.peppol import KSeFPeppolUBLParser, KSeFPeppolUBLSerializer

_CUSTOMIZATION_ID = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)
_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"


@pytest.fixture
def peppol_seller() -> KSeFParty:
    return KSeFParty(
        name="Polska Firma S.A.",
        nip="5261040828",
        address=EN16931Address(
            line_one="ul. Nowy Świat 6/12",
            city="Warszawa",
            postcode="00-400",
            country_code="PL",
        ),
    )


@pytest.fixture
def german_buyer() -> KSeFParty:
    return KSeFParty(
        name="Deutsche Firma GmbH",
        eu_vat_country="DE",
        eu_vat_id="123456789",
        address=EN16931Address(
            line_one="Musterstraße 1",
            city="Berlin",
            postcode="10115",
            country_code="DE",
        ),
    )


@pytest.fixture
def peppol_invoice(peppol_seller: KSeFParty, german_buyer: KSeFParty) -> KSeFInvoice:
    return KSeFInvoice(
        profile=_CUSTOMIZATION_ID,
        invoice_number="PL/2024/0042",
        invoice_date=date(2024, 6, 1),
        invoice_type_code="380",
        currency_code="EUR",
        seller=peppol_seller,
        buyer=german_buyer,
        sum_of_line_net_amounts=Decimal("1000.00"),
        tax_exclusive_amount=Decimal("1000.00"),
        tax_total=Decimal("230.00"),
        tax_inclusive_amount=Decimal("1230.00"),
        amount_due=Decimal("1230.00"),
        tax_lines=[
            EN16931Tax(
                category="S",
                rate=Decimal("23"),
                taxable_amount=Decimal("1000.00"),
                tax_amount=Decimal("230.00"),
            )
        ],
        line_items=[
            EN16931LineItem(
                line_id="1",
                name="Consulting services",
                quantity=Decimal("10"),
                unit_code="HUR",
                unit_price=Decimal("100.00"),
                line_net_amount=Decimal("1000.00"),
                tax_category="S",
                tax_rate=Decimal("23"),
            )
        ],
    )


@pytest.fixture
def serializer() -> KSeFPeppolUBLSerializer:
    return KSeFPeppolUBLSerializer()


@pytest.fixture
def parser() -> KSeFPeppolUBLParser:
    return KSeFPeppolUBLParser()


class TestKSeFPeppolUBLSerializer:
    def test_produces_bytes(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        result = serializer.serialize(peppol_invoice)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_customization_id_present(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        xml = serializer.serialize(peppol_invoice).decode()
        assert _CUSTOMIZATION_ID in xml

    def test_profile_id_injected(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        xml = serializer.serialize(peppol_invoice).decode()
        assert _PROFILE_ID in xml
        assert "<cbc:ProfileID>" in xml

    def test_profile_id_after_customization_id(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        xml = serializer.serialize(peppol_invoice).decode()
        cust_pos = xml.index(_CUSTOMIZATION_ID)
        profile_pos = xml.index(_PROFILE_ID)
        assert profile_pos > cust_pos

    def test_profile_id_emitted_exactly_once(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        """PL-PEP-1 regression guard: after removing the ad-hoc ProfileID
        injection overrides in favour of core's business_process-driven
        emission (core v1.15.0), the element must not be double-emitted."""
        xml = serializer.serialize(peppol_invoice).decode()
        assert xml.count("<cbc:ProfileID>") == 1

    def test_business_process_respected_when_caller_sets_it(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        peppol_invoice.business_process = "urn:peppol:pint:billing-1"
        xml = serializer.serialize(peppol_invoice).decode()
        assert xml.count("<cbc:ProfileID>") == 1
        assert "urn:peppol:pint:billing-1" in xml

    def test_nip_mapped_to_pl_prefix(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        xml = serializer.serialize(peppol_invoice).decode()
        assert "PL5261040828" in xml

    def test_eu_buyer_vat_id(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        xml = serializer.serialize(peppol_invoice).decode()
        assert "DE123456789" in xml

    def test_invoice_number_and_date(
        self, serializer: KSeFPeppolUBLSerializer, peppol_invoice: KSeFInvoice
    ) -> None:
        xml = serializer.serialize(peppol_invoice).decode()
        assert "PL/2024/0042" in xml
        assert "2024-06-01" in xml

    def test_party_without_address_uses_fallback(
        self, serializer: KSeFPeppolUBLSerializer
    ) -> None:
        seller = KSeFParty(name="No Address Seller", nip="5261040828", address=None)
        buyer = KSeFParty(
            name="Buyer", eu_vat_country="DE", eu_vat_id="123456789", address=None
        )
        invoice = KSeFInvoice(
            profile=_CUSTOMIZATION_ID,
            invoice_number="TEST/001",
            invoice_date=date(2024, 1, 1),
            invoice_type_code="380",
            currency_code="PLN",
            seller=seller,
            buyer=buyer,
            sum_of_line_net_amounts=Decimal("100.00"),
            tax_exclusive_amount=Decimal("100.00"),
            tax_total=Decimal("23.00"),
            tax_inclusive_amount=Decimal("123.00"),
            amount_due=Decimal("123.00"),
            tax_lines=[
                EN16931Tax(
                    category="S",
                    rate=Decimal("23"),
                    taxable_amount=Decimal("100.00"),
                    tax_amount=Decimal("23.00"),
                )
            ],
            line_items=[
                EN16931LineItem(
                    line_id="1",
                    name="Service",
                    quantity=Decimal("1"),
                    unit_code="C62",
                    unit_price=Decimal("100.00"),
                    line_net_amount=Decimal("100.00"),
                    tax_category="S",
                    tax_rate=Decimal("23"),
                )
            ],
        )
        xml = serializer.serialize(invoice).decode()
        assert "PL5261040828" in xml
        assert "DE123456789" in xml


class TestKSeFPeppolUBLParser:
    def test_round_trip_type(
        self,
        serializer: KSeFPeppolUBLSerializer,
        parser: KSeFPeppolUBLParser,
        peppol_invoice: KSeFInvoice,
    ) -> None:
        xml_bytes = serializer.serialize(peppol_invoice)
        result = parser.parse(xml_bytes)
        assert isinstance(result, KSeFInvoice)

    def test_round_trip_seller_is_ksef_party(
        self,
        serializer: KSeFPeppolUBLSerializer,
        parser: KSeFPeppolUBLParser,
        peppol_invoice: KSeFInvoice,
    ) -> None:
        xml_bytes = serializer.serialize(peppol_invoice)
        result = parser.parse(xml_bytes)
        assert isinstance(result.seller, KSeFParty)
        assert isinstance(result.buyer, KSeFParty)

    def test_round_trip_nip_extracted(
        self,
        serializer: KSeFPeppolUBLSerializer,
        parser: KSeFPeppolUBLParser,
        peppol_invoice: KSeFInvoice,
    ) -> None:
        xml_bytes = serializer.serialize(peppol_invoice)
        result = parser.parse(xml_bytes)
        assert result.seller.nip == "5261040828"

    def test_round_trip_eu_vat_extracted(
        self,
        serializer: KSeFPeppolUBLSerializer,
        parser: KSeFPeppolUBLParser,
        peppol_invoice: KSeFInvoice,
    ) -> None:
        xml_bytes = serializer.serialize(peppol_invoice)
        result = parser.parse(xml_bytes)
        assert result.buyer.eu_vat_country == "DE"
        assert result.buyer.eu_vat_id == "123456789"

    def test_round_trip_invoice_fields(
        self,
        serializer: KSeFPeppolUBLSerializer,
        parser: KSeFPeppolUBLParser,
        peppol_invoice: KSeFInvoice,
    ) -> None:
        xml_bytes = serializer.serialize(peppol_invoice)
        result = parser.parse(xml_bytes)
        assert result.invoice_number == peppol_invoice.invoice_number
        assert result.invoice_date == peppol_invoice.invoice_date
        assert result.currency_code == peppol_invoice.currency_code
        assert result.amount_due == peppol_invoice.amount_due

    def test_numer_ksef_is_none(
        self,
        serializer: KSeFPeppolUBLSerializer,
        parser: KSeFPeppolUBLParser,
        peppol_invoice: KSeFInvoice,
    ) -> None:
        xml_bytes = serializer.serialize(peppol_invoice)
        result = parser.parse(xml_bytes)
        assert result.numer_ksef is None
