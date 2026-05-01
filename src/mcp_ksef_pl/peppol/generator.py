"""Peppol BIS Billing 3.0 / EN 16931 UBL 2.1 invoice generator for Poland."""

from decimal import ROUND_HALF_UP, Decimal

from mcp_einvoicing_core import (
    BaseDocumentGenerator,
    DocumentGenerationError,
    InvoiceDocument,
    InvoiceParty,
    VATSummary,
    format_amount,
    xml_optional,
)
from mcp_einvoicing_core.xml_utils import xml_escape

_CUSTOMIZATION_ID = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)
_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

_NS_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
_NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"


def _d(value: Decimal) -> str:
    return format_amount(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _party_block(party: InvoiceParty, tag: str) -> str:
    name = party.name or f"{party.first_name or ''} {party.last_name or ''}".strip()
    nip = party.tax_id.identifier
    country = party.tax_id.country_code.upper()

    addr = ""
    if party.address:
        a = party.address
        addr = (
            f"        <cac:PostalAddress>\n"
            + (f"          <cbc:StreetName>{xml_escape(a.street or '')}</cbc:StreetName>\n" if a.street else "")
            + (f"          <cbc:CityName>{xml_escape(a.city or '')}</cbc:CityName>\n" if a.city else "")
            + (f"          <cbc:PostalZone>{xml_escape(a.postal_code or '')}</cbc:PostalZone>\n" if a.postal_code else "")
            + f"          <cac:Country>\n"
            f"            <cbc:IdentificationCode>{xml_escape(a.country_code.upper())}</cbc:IdentificationCode>\n"
            f"          </cac:Country>\n"
            f"        </cac:PostalAddress>\n"
        )

    return (
        f"    <{tag}>\n"
        f"      <cac:Party>\n"
        f"        <cac:PartyName><cbc:Name>{xml_escape(name)}</cbc:Name></cac:PartyName>\n"
        f"{addr}"
        f"        <cac:PartyTaxScheme>\n"
        f"          <cbc:CompanyID>{xml_escape(country)}{xml_escape(nip)}</cbc:CompanyID>\n"
        f"          <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>\n"
        f"        </cac:PartyTaxScheme>\n"
        f"        <cac:PartyLegalEntity>\n"
        f"          <cbc:RegistrationName>{xml_escape(name)}</cbc:RegistrationName>\n"
        f"        </cac:PartyLegalEntity>\n"
        f"      </cac:Party>\n"
        f"    </{tag}>\n"
    )


def _tax_total(summaries: list[VATSummary], currency: str) -> str:
    total_tax = sum(s.vat_amount for s in summaries)
    subtotals = ""
    for s in summaries:
        rate_str = _d(s.vat_rate)
        cat_id = "S" if s.vat_rate > 0 else ("E" if s.vat_exemption_code else "Z")
        subtotals += (
            f"    <cac:TaxSubtotal>\n"
            f"      <cbc:TaxableAmount currencyID=\"{xml_escape(currency)}\">{_d(s.taxable_base)}</cbc:TaxableAmount>\n"
            f"      <cbc:TaxAmount currencyID=\"{xml_escape(currency)}\">{_d(s.vat_amount)}</cbc:TaxAmount>\n"
            f"      <cac:TaxCategory>\n"
            f"        <cbc:ID>{cat_id}</cbc:ID>\n"
            f"        <cbc:Percent>{rate_str}</cbc:Percent>\n"
            f"        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>\n"
            f"      </cac:TaxCategory>\n"
            f"    </cac:TaxSubtotal>\n"
        )
    return (
        f"  <cac:TaxTotal>\n"
        f"    <cbc:TaxAmount currencyID=\"{xml_escape(currency)}\">{_d(total_tax)}</cbc:TaxAmount>\n"
        f"{subtotals}"
        f"  </cac:TaxTotal>\n"
    )


def _monetary_total(invoice: InvoiceDocument) -> str:
    summaries = invoice.vat_summary or []
    line_ext = sum(s.taxable_base for s in summaries)
    tax_excl = line_ext
    tax_incl = line_ext + sum(s.vat_amount for s in summaries)
    cur = invoice.currency

    return (
        f"  <cac:LegalMonetaryTotal>\n"
        f"    <cbc:LineExtensionAmount currencyID=\"{xml_escape(cur)}\">{_d(line_ext)}</cbc:LineExtensionAmount>\n"
        f"    <cbc:TaxExclusiveAmount currencyID=\"{xml_escape(cur)}\">{_d(tax_excl)}</cbc:TaxExclusiveAmount>\n"
        f"    <cbc:TaxInclusiveAmount currencyID=\"{xml_escape(cur)}\">{_d(tax_incl)}</cbc:TaxInclusiveAmount>\n"
        f"    <cbc:PayableAmount currencyID=\"{xml_escape(cur)}\">{_d(tax_incl)}</cbc:PayableAmount>\n"
        f"  </cac:LegalMonetaryTotal>\n"
    )


def _invoice_lines(invoice: InvoiceDocument) -> str:
    lines = ""
    for line in invoice.lines:
        rate = _d(line.vat_rate)
        cat_id = "S" if line.vat_rate > 0 else ("E" if line.vat_exemption_code else "Z")
        lines += (
            f"  <cac:InvoiceLine>\n"
            f"    <cbc:ID>{line.line_number}</cbc:ID>\n"
            f"    <cbc:InvoicedQuantity unitCode=\"{xml_escape(line.unit_of_measure or 'C62')}\">"
            f"{format_amount(line.quantity)}</cbc:InvoicedQuantity>\n"
            f"    <cbc:LineExtensionAmount currencyID=\"{xml_escape(invoice.currency)}\">"
            f"{_d(line.total_price)}</cbc:LineExtensionAmount>\n"
            f"    <cac:Item>\n"
            f"      <cbc:Description>{xml_escape(line.description)}</cbc:Description>\n"
            f"      <cbc:Name>{xml_escape(line.description)}</cbc:Name>\n"
            f"      <cac:ClassifiedTaxCategory>\n"
            f"        <cbc:ID>{cat_id}</cbc:ID>\n"
            f"        <cbc:Percent>{rate}</cbc:Percent>\n"
            f"        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>\n"
            f"      </cac:ClassifiedTaxCategory>\n"
            f"    </cac:Item>\n"
            f"    <cac:Price>\n"
            f"      <cbc:PriceAmount currencyID=\"{xml_escape(invoice.currency)}\">"
            f"{_d(line.unit_price)}</cbc:PriceAmount>\n"
            f"    </cac:Price>\n"
            f"  </cac:InvoiceLine>\n"
        )
    return lines


class PeppolUBLGenerator(BaseDocumentGenerator):
    """Generates Peppol BIS Billing 3.0 UBL 2.1 invoices (EN 16931)."""

    def get_format_name(self) -> str:
        return "Peppol-BIS-3.0-UBL"

    def get_country_code(self) -> str:
        return "PL"

    def get_namespace(self) -> str:
        return _NS_INVOICE

    async def generate(self, invoice: InvoiceDocument) -> str:
        try:
            invoice_type_code = "380"  # Commercial invoice; 381 = credit note

            xml = (
                f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<Invoice xmlns="{_NS_INVOICE}"\n'
                f'         xmlns:cac="{_NS_CAC}"\n'
                f'         xmlns:cbc="{_NS_CBC}">\n'
                f"  <cbc:CustomizationID>{_CUSTOMIZATION_ID}</cbc:CustomizationID>\n"
                f"  <cbc:ProfileID>{_PROFILE_ID}</cbc:ProfileID>\n"
                f"  <cbc:ID>{xml_escape(invoice.number)}</cbc:ID>\n"
                f"  <cbc:IssueDate>{xml_escape(str(invoice.date))}</cbc:IssueDate>\n"
                f"  <cbc:InvoiceTypeCode>{invoice_type_code}</cbc:InvoiceTypeCode>\n"
                f"  <cbc:DocumentCurrencyCode>{xml_escape(invoice.currency)}</cbc:DocumentCurrencyCode>\n"
                + (f"  <cbc:Note>{xml_escape(invoice.note)}</cbc:Note>\n" if invoice.note else "")
                + _party_block(invoice.seller, "cac:AccountingSupplierParty")
                + _party_block(invoice.buyer, "cac:AccountingCustomerParty")
                + _tax_total(invoice.vat_summary or [], invoice.currency)
                + _monetary_total(invoice)
                + _invoice_lines(invoice)
                + f"</Invoice>\n"
            )
            return xml
        except Exception as exc:
            raise DocumentGenerationError(f"Peppol UBL generation failed: {exc}") from exc
