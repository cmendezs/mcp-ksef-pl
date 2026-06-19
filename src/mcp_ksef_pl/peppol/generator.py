"""Peppol BIS Billing 3.0 / EN 16931 UBL 2.1 invoice generator for Poland."""

from decimal import ROUND_HALF_UP, Decimal

from mcp_einvoicing_core import (
    BaseDocumentGenerator,
    DocumentGenerationError,
    format_amount,
)
from mcp_einvoicing_core.en16931 import EN16931Tax
from mcp_einvoicing_core.xml_utils import xml_escape

from mcp_ksef_pl.models import KSeFInvoice, KSeFParty

_CUSTOMIZATION_ID = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)
_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

_NS_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
_NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"


def _d(value: Decimal) -> str:
    return format_amount(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _party_block(party: KSeFParty, tag: str) -> str:
    nip = party.nip or ""
    country = (party.eu_vat_country or "PL").upper()

    addr = ""
    if party.address:
        a = party.address
        addr = (
            "        <cac:PostalAddress>\n"
            + f"          <cbc:StreetName>{xml_escape(a.line_one)}</cbc:StreetName>\n"
            + f"          <cbc:CityName>{xml_escape(a.city)}</cbc:CityName>\n"
            + f"          <cbc:PostalZone>{xml_escape(a.postcode)}</cbc:PostalZone>\n"
            + "          <cac:Country>\n"
            f"            <cbc:IdentificationCode>"
            f"{xml_escape(a.country_code.upper())}</cbc:IdentificationCode>\n"
            f"          </cac:Country>\n"
            f"        </cac:PostalAddress>\n"
        )

    return (
        f"    <{tag}>\n"
        f"      <cac:Party>\n"
        f"        <cac:PartyName><cbc:Name>{xml_escape(party.name)}</cbc:Name></cac:PartyName>\n"
        f"{addr}"
        f"        <cac:PartyTaxScheme>\n"
        f"          <cbc:CompanyID>{xml_escape(country)}{xml_escape(nip)}</cbc:CompanyID>\n"
        f"          <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>\n"
        f"        </cac:PartyTaxScheme>\n"
        f"        <cac:PartyLegalEntity>\n"
        f"          <cbc:RegistrationName>{xml_escape(party.name)}</cbc:RegistrationName>\n"
        f"        </cac:PartyLegalEntity>\n"
        f"      </cac:Party>\n"
        f"    </{tag}>\n"
    )


def _tax_total(summaries: list[EN16931Tax], currency: str) -> str:
    total_tax = sum(s.tax_amount for s in summaries)
    subtotals = ""
    cur = xml_escape(currency)
    for s in summaries:
        rate_str = _d(s.rate)
        # s.category is already UNCL5305 (S, E, AE, O, Z, etc.)
        cat_id = s.category
        subtotals += (
            f"    <cac:TaxSubtotal>\n"
            f"      <cbc:TaxableAmount currencyID=\"{cur}\">"
            f"{_d(s.taxable_amount)}</cbc:TaxableAmount>\n"
            f"      <cbc:TaxAmount currencyID=\"{cur}\">{_d(s.tax_amount)}</cbc:TaxAmount>\n"
            f"      <cac:TaxCategory>\n"
            f"        <cbc:ID>{xml_escape(cat_id)}</cbc:ID>\n"
            f"        <cbc:Percent>{rate_str}</cbc:Percent>\n"
            f"        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>\n"
            f"      </cac:TaxCategory>\n"
            f"    </cac:TaxSubtotal>\n"
        )
    return (
        f"  <cac:TaxTotal>\n"
        f"    <cbc:TaxAmount currencyID=\"{cur}\">{_d(total_tax)}</cbc:TaxAmount>\n"
        f"{subtotals}"
        f"  </cac:TaxTotal>\n"
    )


def _monetary_total(invoice: KSeFInvoice) -> str:
    esc_cur = xml_escape(invoice.currency_code)

    return (
        f"  <cac:LegalMonetaryTotal>\n"
        f"    <cbc:LineExtensionAmount currencyID=\"{esc_cur}\">"
        f"{_d(invoice.sum_of_line_net_amounts)}</cbc:LineExtensionAmount>\n"
        f"    <cbc:TaxExclusiveAmount currencyID=\"{esc_cur}\">"
        f"{_d(invoice.tax_exclusive_amount)}</cbc:TaxExclusiveAmount>\n"
        f"    <cbc:TaxInclusiveAmount currencyID=\"{esc_cur}\">"
        f"{_d(invoice.tax_inclusive_amount)}</cbc:TaxInclusiveAmount>\n"
        f"    <cbc:PayableAmount currencyID=\"{esc_cur}\">"
        f"{_d(invoice.amount_due)}</cbc:PayableAmount>\n"
        f"  </cac:LegalMonetaryTotal>\n"
    )


def _invoice_lines(invoice: KSeFInvoice) -> str:
    lines = ""
    for line in invoice.line_items:
        rate = _d(line.tax_rate)
        cat_id = line.tax_category
        lines += (
            f"  <cac:InvoiceLine>\n"
            f"    <cbc:ID>{xml_escape(line.line_id)}</cbc:ID>\n"
            f"    <cbc:InvoicedQuantity unitCode=\"{xml_escape(line.unit_code or 'C62')}\">"
            f"{format_amount(line.quantity)}</cbc:InvoicedQuantity>\n"
            f"    <cbc:LineExtensionAmount currencyID=\"{xml_escape(invoice.currency_code)}\">"
            f"{_d(line.line_net_amount)}</cbc:LineExtensionAmount>\n"
            f"    <cac:Item>\n"
            f"      <cbc:Description>{xml_escape(line.name)}</cbc:Description>\n"
            f"      <cbc:Name>{xml_escape(line.name)}</cbc:Name>\n"
            f"      <cac:ClassifiedTaxCategory>\n"
            f"        <cbc:ID>{xml_escape(cat_id)}</cbc:ID>\n"
            f"        <cbc:Percent>{rate}</cbc:Percent>\n"
            f"        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>\n"
            f"      </cac:ClassifiedTaxCategory>\n"
            f"    </cac:Item>\n"
            f"    <cac:Price>\n"
            f"      <cbc:PriceAmount currencyID=\"{xml_escape(invoice.currency_code)}\">"
            f"{_d(line.unit_price)}</cbc:PriceAmount>\n"
            f"    </cac:Price>\n"
            f"  </cac:InvoiceLine>\n"
        )
    return lines


class PeppolUBLGenerator(BaseDocumentGenerator[KSeFInvoice]):
    """Generates Peppol BIS Billing 3.0 UBL 2.1 invoices (EN 16931)."""

    def get_format_name(self) -> str:
        return "Peppol-BIS-3.0-UBL"

    def get_country_code(self) -> str:
        return "PL"

    def get_namespace(self) -> str:
        return _NS_INVOICE

    async def generate(self, invoice: KSeFInvoice) -> str:
        try:
            invoice_type_code = "380"  # Commercial invoice; 381 = credit note

            xml = (
                f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<Invoice xmlns="{_NS_INVOICE}"\n'
                f'         xmlns:cac="{_NS_CAC}"\n'
                f'         xmlns:cbc="{_NS_CBC}">\n'
                f"  <cbc:CustomizationID>{_CUSTOMIZATION_ID}</cbc:CustomizationID>\n"
                f"  <cbc:ProfileID>{_PROFILE_ID}</cbc:ProfileID>\n"
                f"  <cbc:ID>{xml_escape(invoice.invoice_number)}</cbc:ID>\n"
                f"  <cbc:IssueDate>{xml_escape(str(invoice.invoice_date))}</cbc:IssueDate>\n"
                f"  <cbc:InvoiceTypeCode>{invoice_type_code}</cbc:InvoiceTypeCode>\n"
                f"  <cbc:DocumentCurrencyCode>"
                f"{xml_escape(invoice.currency_code)}</cbc:DocumentCurrencyCode>\n"
                + (f"  <cbc:Note>{xml_escape(invoice.note)}</cbc:Note>\n" if invoice.note else "")
                + _party_block(invoice.seller, "cac:AccountingSupplierParty")
                + _party_block(invoice.buyer, "cac:AccountingCustomerParty")
                + _tax_total(invoice.tax_lines or [], invoice.currency_code)
                + _monetary_total(invoice)
                + _invoice_lines(invoice)
                + "</Invoice>\n"
            )
            return xml
        except Exception as exc:
            raise DocumentGenerationError(f"Peppol UBL generation failed: {exc}") from exc
