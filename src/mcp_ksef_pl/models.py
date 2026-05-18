"""KSeF-specific Pydantic models for mcp-ksef-pl.

KSeFInvoice subclasses EN16931Invoice rather than InvoiceDocument because Polish
VAT invoices are semantically EN 16931 compliant: the data model is the same; the
KSeF XML serialisation format (FA(2)/FA(3)) is a national schema that generators
map to from this shared base.

The generators in generator.py currently accept InvoiceDocument for backward
compatibility.  The intended migration path (PL-5.1, roadmap Q3 2026) is:
  1. Change tool function signatures (server.py) from InvoiceDocument to KSeFInvoice.
  2. Migrate generator functions to read EN16931Invoice field names:
       invoice.number        → invoice.invoice_number
       invoice.date          → invoice.invoice_date  (date object, not str)
       invoice.currency      → invoice.currency_code
       invoice.lines         → invoice.line_items    (list[EN16931LineItem])
       invoice.vat_summary   → invoice.tax_lines     (list[EN16931Tax])
       invoice.payment       → invoice.payment_means (EN16931PaymentMeans | None)
       invoice.payment.due_date → invoice.due_date   (moved to invoice level)
       line.line_number      → line.line_id           (str, not int)
       line.description      → line.name
       line.unit_of_measure  → line.unit_code
       line.total_price      → line.line_net_amount
       line.vat_rate         → line.tax_rate
       s.vat_rate            → s.rate
       s.taxable_base        → s.taxable_amount
       s.vat_amount          → s.tax_amount
       s.vat_exemption_code  → s.category (UNCL5305: E=ZW, AE=OO, O=NP)
  3. Remove InvoiceDocument and VATSummary imports from generator.py.
  NOTE: EN16931Invoice has mandatory financial total fields (sum_of_line_net_amounts,
  tax_exclusive_amount, tax_total, tax_inclusive_amount, amount_due) that are absent
  from InvoiceDocument.  The tool API must remain on InvoiceDocument until those
  totals can be auto-computed from line items in a pre-generation step.

KSeF-specific extensions layered on top of EN 16931:
  - numer_ksef:      post-clearance reference number issued by the KSeF platform
  - _require_tax_lines relaxed: KSeF supports summary-only (MINIMUM-equivalent)
    documents that carry only document totals and no line-level VAT breakdown

[NEED: confirm whether KSeF FA(3) mandates tax_lines for all invoice types or
 only for detailed (szczegolowy) invoices — check schemat_FA(3)_v1-0E.xsd.]
"""

from __future__ import annotations

from mcp_einvoicing_core.en16931 import EN16931Invoice, EN16931Party
from pydantic import BaseModel, Field, field_validator, model_validator


class KSeFParty(EN16931Party):
    """KSeF trading party extending EN16931Party with NIP support.

    KSeF requires NIP (Numer Identyfikacji Podatkowej) for PL taxpayers.
    For cross-border invoices where the seller/buyer does not have a NIP,
    the EU VAT number is carried via the inherited vat_id field.
    The KSeF generators extract the NIP from tax_id.identifier when
    tax_id.country_code == "PL".

    GLN is carried on party.address.gln (core PartyAddress field) and emitted
    as <GLN> in TAdres blocks by the FA(2)/FA(3) generators when present.
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


# ---------------------------------------------------------------------------
# FA(3) optional extension types (PL-2.2, PL-2.3, PL-2.4, PL-4.1)
# ---------------------------------------------------------------------------


class KSeFAttachment(BaseModel):
    """Supporting document attachment for FA(3) <Zalacznik>.

    KSeF imposes a maximum attachment payload size (check ksef-api-v2-openapi.json
    for the current limit before encoding large files).
    """

    filename: str = Field(..., description="Original filename including extension")
    mime_type: str = Field(..., description="MIME type, e.g. 'application/pdf'")
    content_base64: str = Field(..., description="Base64-encoded file content")

    @field_validator("content_base64")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content_base64 must not be empty")
        return v


class KSeFPodmiot3(BaseModel):
    """Additional party on the invoice — FA(3) <Podmiot3>.

    Used when JST=1 (local-government sub-unit) or to identify a third party
    (e.g. factoring recipient, secondary buyer). Up to 100 entries per invoice.

    role_code: 1=nabywca(buyer), 2=zamawiający(ordering), 3=faktorant(factoring),
               4=odbiorca(recipient), 5=inny(other).
    """

    nip: str = Field("", description="Polish NIP (10 digits)")
    name: str = Field(..., description="Entity name")
    role_code: str = Field("5", description="Role code (1-5)")
    role_description: str | None = Field(None, description="Free-text role description")


class KSeFPodmiotUpowazniony(BaseModel):
    """Authorised representative — FA(3) <PodmiotUpowazniony>.

    Identifies an entity authorised to issue invoices on behalf of the seller.
    """

    nip: str = Field(..., description="Polish NIP (10 digits)")
    name: str = Field(..., description="Entity name")


class KSeFCorrectionRef(BaseModel):
    """Reference to the original invoice being corrected — FA(3) correction block.

    Exactly one of numer_ksef, numer_ksefn, or numer_ksefzn must be supplied:
      numer_ksef   — KSeF reference of the accepted original (most common)
      numer_ksefn  — KSeF reference of a note-corrected original
      numer_ksefzn — KSeF zero-invoice reference (for full reversal)
    """

    numer_ksef: str = Field("", description="KSeF number of the original invoice")
    numer_ksefn: str = Field("", description="KSeF number (note-corrected original)")
    numer_ksefzn: str = Field("", description="KSeF zero-invoice reference")


class KSeFFA3Options(BaseModel):
    """Optional FA(3) extensions passed alongside InvoiceDocument to generate_fa3_invoice.

    All fields are optional and default to no-op values so callers that do not
    need any extension can omit this parameter entirely.
    """

    # PL-2.2 — KSeF payment identifiers
    ipksef: str = Field("", description="KSeF payment identifier (IPKSeF)")
    link_do_platnosci: str = Field(
        "",
        description=(
            "URL to the KSeF payment portal. Must match the pattern "
            "https?://...?IPKSeF=<digits><alphanum> per the FA(3) XSD regex."
        ),
    )

    # PL-4.1 — invoice type and correction reference
    rodzaj_faktury: str = Field(
        "VAT",
        description=(
            "Invoice type: VAT (standard), KOR (correction), ZAL (advance), "
            "ROZ (settlement), UPR (simplified), KOR_ZAL (advance correction), "
            "KOR_ROZ (settlement correction)"
        ),
    )
    correction: KSeFCorrectionRef | None = Field(
        None,
        description="Correction reference block — required when rodzaj_faktury=KOR",
    )

    # PL-2.3 — attachments
    attachments: list[KSeFAttachment] | None = Field(
        None, description="Supporting document attachments (<Zalacznik>)"
    )

    # PL-2.4 — additional parties
    podmiot3_entries: list[KSeFPodmiot3] | None = Field(
        None, description="Additional buyer / third-party entities (<Podmiot3>)"
    )
    podmiot_upowazniony: KSeFPodmiotUpowazniony | None = Field(
        None,
        description="Authorised representative (<PodmiotUpowazniony>)",
    )
