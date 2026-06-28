"""KSeF-specific Pydantic models for mcp-ksef-pl.

KSeFInvoice subclasses EN16931Invoice because Polish VAT invoices are
semantically EN 16931 compliant. The KSeF XML formats (FA(2)/FA(3)) are
national schemas that generators map to from this shared base.

Tool functions in server.py accept KSeFInvoice directly. The from_lines()
classmethod auto-computes the mandatory EN 16931 financial totals from
line items and tax lines.

KSeF-specific extensions layered on top of EN 16931:
  - numer_ksef:      post-clearance reference number issued by the KSeF platform
  - _require_tax_lines relaxed: FA(3) XSD declares FaWiersz with minOccurs=0,
    confirming that line items (and by extension line-level VAT) are optional
    for advance invoices (zaliczkowa) and certain correction invoices
"""

from __future__ import annotations

from decimal import Decimal

from mcp_einvoicing_core.en16931 import (
    EN16931Address,
    EN16931Invoice,
    EN16931LineItem,
    EN16931Party,
    EN16931Tax,
)
from pydantic import BaseModel, Field, field_validator, model_validator


class KSeFParty(EN16931Party):
    """KSeF trading party extending EN16931Party with Polish NIP and EU VAT fields.

    KSeF requires NIP (Numer Identyfikacji Podatkowej) for PL taxpayers.
    For cross-border invoices where the seller/buyer does not have a NIP,
    the EU VAT country and number are carried via eu_vat_country / eu_vat_id.

    address is overridden to Optional so that cross-border parties without a
    Polish address can be represented (BrakID path in FA(3) buyer block).

    GLN is carried at the party level and emitted as <GLN> in TAdres blocks
    by the FA(2)/FA(3) generators when present.
    """

    address: EN16931Address | None = None  # type: ignore[assignment]
    nip: str | None = Field(None, description="Polish NIP (10 digits)")
    eu_vat_country: str | None = Field(
        None, description="EU VAT country code for non-PL sellers/buyers"
    )
    eu_vat_id: str | None = Field(
        None, description="EU VAT number for non-PL sellers/buyers"
    )
    gln: str | None = Field(None, description="GS1 Global Location Number")

    @model_validator(mode="after")
    def _sync_nip_to_vat_id(self) -> KSeFParty:
        if self.nip and not self.vat_id:
            self.vat_id = f"PL{self.nip}"
        return self


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
        # FA(3) XSD: FaWiersz minOccurs=0; line-level VAT is optional for
        # advance and certain correction invoices.
        return self

    @classmethod
    def from_lines(cls, **kwargs: object) -> KSeFInvoice:
        """Construct a KSeFInvoice, auto-computing financial totals from line_items/tax_lines.

        Callers may omit sum_of_line_net_amounts, tax_exclusive_amount,
        tax_total, tax_inclusive_amount, and amount_due; they will be
        derived from the provided line_items and tax_lines.
        """
        line_items: list[EN16931LineItem] = kwargs.get("line_items", [])  # type: ignore[assignment]
        tax_lines: list[EN16931Tax] = kwargs.get("tax_lines", [])  # type: ignore[assignment]

        sum_of_lines = sum((li.line_net_amount for li in line_items), Decimal("0"))
        tax_total = sum((t.tax_amount for t in tax_lines), Decimal("0"))
        tax_excl = (
            sum((t.taxable_amount for t in tax_lines), Decimal("0"))
            if tax_lines
            else sum_of_lines
        )
        tax_incl = tax_excl + tax_total

        kwargs.setdefault("sum_of_line_net_amounts", sum_of_lines)  # type: ignore[union-attr]
        kwargs.setdefault("tax_exclusive_amount", tax_excl)  # type: ignore[union-attr]
        kwargs.setdefault("tax_total", tax_total)  # type: ignore[union-attr]
        kwargs.setdefault("tax_inclusive_amount", tax_incl)  # type: ignore[union-attr]
        kwargs.setdefault("amount_due", tax_incl)  # type: ignore[union-attr]

        return cls(**kwargs)  # type: ignore[arg-type]


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
    """Optional FA(3) extensions passed alongside KSeFInvoice to generate_fa3_invoice.

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
