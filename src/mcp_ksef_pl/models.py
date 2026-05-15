"""KSeF-specific Pydantic models for mcp-ksef-pl.

KSeFInvoice subclasses EN16931Invoice rather than InvoiceDocument because Polish
VAT invoices are semantically EN 16931 compliant: the data model is the same; the
KSeF XML serialisation format (FA(2)/FA(3)) is a national schema that generators
map to from this shared base.

The generators in generator.py currently accept InvoiceDocument for backward
compatibility.  The intended migration path is:
  1. Instantiate KSeFInvoice from tool inputs (this file provides the model).
  2. Migrate generator functions to read EN16931Invoice field names
     (invoice_number, invoice_date, line_items, tax_lines, payment_means).
  3. Remove InvoiceDocument imports from generator.py.

KSeF-specific extensions layered on top of EN 16931:
  - numer_ksef:      post-clearance reference number issued by the KSeF platform
  - _require_tax_lines relaxed: KSeF supports summary-only (MINIMUM-equivalent)
    documents that carry only document totals and no line-level VAT breakdown

[NEED: confirm whether KSeF FA(3) mandates tax_lines for all invoice types or
 only for detailed (szczegolowy) invoices — check schemat_FA(3)_v1-0E.xsd.]
"""

from __future__ import annotations

from mcp_einvoicing_core.en16931 import EN16931Invoice, EN16931Party
from pydantic import Field, model_validator


class KSeFParty(EN16931Party):
    """KSeF trading party extending EN16931Party with NIP support.

    KSeF requires NIP (Numer Identyfikacji Podatkowej) for PL taxpayers.
    For cross-border invoices where the seller/buyer does not have a NIP,
    the EU VAT number is carried via the inherited vat_id field.
    The KSeF generators extract the NIP from tax_id.identifier when
    tax_id.country_code == "PL".
    """

    pass


class KSeFInvoice(EN16931Invoice):
    """EN 16931 invoice extended for KSeF FA(2)/FA(3) submission.

    National extensions:
      numer_ksef  — KSeF reference number, assigned by the platform post-clearance.
                    Not present on the outbound document; populated from the
                    clearance response and stored here for tracking.

    The _allowed_profiles class variable is left as None because KSeF does not
    use EN 16931 GuidelineID URNs. The profile field should be set to the KSeF
    schema identifier or left to the generating tool's convention.
    """

    seller: KSeFParty = Field(..., description="Seller / supplier (BG-4)")
    buyer: KSeFParty = Field(..., description="Buyer / customer (BG-7)")
    numer_ksef: str | None = Field(
        None,
        description=(
            "KSeF reference number assigned by the platform after clearance. "
            "Format: NIP(10) + date(8) + sequence(20) + checksum(2). "
            "Not emitted in the outbound XML; used for lifecycle tracking."
        ),
    )

    @model_validator(mode="after")
    def _require_tax_lines(self) -> KSeFInvoice:
        # KSeF supports summary-only documents (no line-level VAT breakdown).
        # The inherited EN 16931 BR-CO-18 check is intentionally relaxed here.
        return self
