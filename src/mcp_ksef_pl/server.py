"""MCP server entry-point for mcp-ksef-pl.

Exposes tools for generating, validating, parsing, submitting, and querying
Polish KSeF (FA(2)) and Peppol BIS 3.0 / EN 16931 electronic invoices.
"""

from __future__ import annotations

from typing import Any

from mcp_einvoicing_core import (
    DocumentValidationResult,
    EInvoicingMCPServer,
)
from mcp_einvoicing_core.base_server import assert_not_read_only
from mcp_einvoicing_core.confirmation import ConfirmationGate
from mcp_einvoicing_core.logging_utils import get_logger, setup_logging
from mcp_einvoicing_core.peppol.tools import register_peppol_tools

from .config import KSeFSettings
from .generator import FA2Generator, FA3Generator
from .lifecycle import KSeFLifecycleManager
from .models import KSeFFA3Options, KSeFInvoice
from .parser import FA2Parser
from .party_validator import PolishPartyValidator, validate_nip, validate_regon
from .peppol import PeppolUBLGenerator
from .peppol.validator import PeppolValidator
from .validator import FA2Validator, FA3Validator

setup_logging()
logger = get_logger(__name__)

_fa2_generator = FA2Generator()
_fa3_generator = FA3Generator()
_fa2_validator = FA2Validator()
_fa3_validator = FA3Validator()
_fa2_parser = FA2Parser()
_peppol_generator = PeppolUBLGenerator()
_peppol_validator = PeppolValidator()
_party_validator = PolishPartyValidator()


def _pl_id_adapter(identifier: str) -> str:
    """Normalize a bare Polish NIP to a Peppol participant ID.

    Scheme 9945 (PL:VAT, "Poland VAT number") per the OpenPeppol eDEC
    Participant Identifier Schemes code list v9.7. Already scheme-qualified
    identifiers (containing ':') pass through unchanged.
    """
    import re

    if ":" in identifier:
        return identifier
    digits = re.sub(r"[\s-]", "", identifier)
    return f"9945:{digits}"


# ---------------------------------------------------------------------------
# FA(2) tools
# ---------------------------------------------------------------------------


async def generate_fa2_invoice(invoice: KSeFInvoice) -> str:
    """Generate a KSeF-compliant FA(2) XML invoice from structured invoice data.

    Returns the FA(2) XML string ready for submission to KSeF.
    The seller's nip must be a Polish NIP (10 digits).
    """
    return await _fa2_generator.generate(invoice)


async def generate_fa3_invoice(
    invoice: KSeFInvoice,
    options: KSeFFA3Options | None = None,
) -> str:
    """Generate a KSeF-compliant FA(3) XML invoice from structured invoice data.

    FA(3) is required for all new invoice submissions via KSeF API v2.
    Use this tool, not generate_fa2_invoice, before calling submit_invoice_to_ksef.

    The seller's nip must be a Polish NIP (10 digits).
    The buyer's nip may be a Polish NIP, eu_vat_country/eu_vat_id for EU
    cross-border, or neither (emits <BrakID>).

    Use the optional `options` parameter to supply:
      - IPKSeF / LinkDoPlatnosci payment identifiers (PL-2.2)
      - Correction invoice reference (rodzaj_faktury=KOR + correction block) (PL-4.1)
      - Supporting document attachments (<Zalacznik>) (PL-2.3)
      - Additional buyer entities (<Podmiot3>) (PL-2.4)
      - Authorised representative (<PodmiotUpowazniony>) (PL-2.4)

    Returns the FA(3) XML string ready for submit_invoice_to_ksef.
    """
    return await _fa3_generator.generate(invoice, options=options)


async def validate_fa2_invoice(xml_content: str) -> DocumentValidationResult:
    """Validate a KSeF FA(2) XML invoice.

    Runs XSD validation (when the official schema is present) and Polish
    business-rule checks.  Returns a DocumentValidationResult with errors and warnings.
    """
    return await _fa2_validator.validate(xml_content)


async def validate_fa3_invoice(xml_content: str) -> DocumentValidationResult:
    """Validate a KSeF FA(3) XML invoice before submission to KSeF API v2 (PL-6.2).

    Runs XSD validation against specs/schemat_FA(3)_v1-0E.xsd (requires lxml)
    and FA(3)-specific business-rule checks including namespace, mandatory
    Adnotacje sub-elements, JST/GV flags, and the absence of the FA(2)
    <FaWiersze> wrapper.

    Call this after generate_fa3_invoice and before submit_invoice_to_ksef.
    Returns a DocumentValidationResult with errors and warnings.
    """
    return await _fa3_validator.validate(xml_content)


async def parse_fa2_invoice(xml_content: str) -> dict[str, Any]:
    """Parse a KSeF FA(2) XML invoice into a structured dictionary.

    Returns a nested dict with 'header', 'seller', 'buyer', 'invoice', and 'lines' keys.
    """
    return await _fa2_parser.parse(xml_content)


# ---------------------------------------------------------------------------
# KSeF lifecycle tools
# ---------------------------------------------------------------------------


async def submit_invoice_to_ksef(
    xml_content: str,
    session_token: str = "",
    session_token_expires_at: str = "",
    confirmation_token: str = "",
) -> dict[str, Any]:
    """Submit a FA(3) XML invoice to the KSeF platform (API v2).

    KSeF API v2 requires FA(3) format for submission.  Use generate_fa3_invoice
    to produce FA(3) XML before calling this tool.

    HUMAN-IN-THE-LOOP: Call without confirmation_token first to receive a
    confirmation summary and token.  Show the summary to the user, then call
    again with confirmation_token set to execute the actual submission.

    Parameters
    ----------
    xml_content:              FA(3) invoice XML string to submit.
    session_token:            KSeF v2 AccessToken (overrides KSEF_SESSION_TOKEN env var).
                              Obtain via the challenge → authenticate → redeem flow:
                              https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md
    session_token_expires_at: ISO-8601 datetime when the token expires.
                              A warning is logged if fewer than 60 seconds remain;
                              submission is blocked if the token is already expired.
    confirmation_token:       Token from the previous awaiting_confirmation response.

    Returns a dict with:
      session_reference  — KSeF session reference number
      invoice_reference  — per-invoice reference number
      reference_number   — "{sessionRef}:{invoiceRef}" for get_ksef_invoice_status
      status             — "submitted"
    """
    assert_not_read_only("KSEF_READ_ONLY")
    _FA3_NS = "http://crd.gov.pl/wzor/2025/06/25/13775/"
    if _FA3_NS not in xml_content:
        from mcp_einvoicing_core import DocumentGenerationError

        raise DocumentGenerationError(
            "xml_content does not appear to be FA(3) XML (namespace not found). "
            "Use generate_fa3_invoice — not generate_fa2_invoice — before calling "
            "submit_invoice_to_ksef."
        )
    gate = ConfirmationGate.get_default()
    token: str | None = confirmation_token or None
    if not gate.is_confirmed(token):
        size_kb = round(len(xml_content.encode()) / 1024, 1)
        return gate.pending_response(
            action="submit_invoice_to_ksef",
            summary=(
                f"Submit a {size_kb} KB FA(3) XML invoice to KSeF (API v2). "
                "This action is irreversible once accepted by the Ministry of Finance platform."
            ),
            token=token,
        )

    settings = KSeFSettings()
    manager = KSeFLifecycleManager(settings)
    metadata: dict[str, Any] = {}
    if session_token:
        metadata["session_token"] = session_token
    if session_token_expires_at:
        metadata["session_token_expires_at"] = session_token_expires_at

    submit_result = await manager.submit_document(xml_content, metadata)
    gate.consume(token)
    return {
        "session_reference": submit_result.session_ref,
        "invoice_reference": submit_result.invoice_ref,
        "reference_number": submit_result.compound_id,
        "status": submit_result.status,
    }


async def get_ksef_invoice_status(reference_number: str) -> dict[str, Any]:
    """Retrieve the processing status of a submitted KSeF invoice (API v2).

    Parameters
    ----------
    reference_number: The 'reference_number' field from submit_invoice_to_ksef
                      ("{sessionRef}:{invoiceRef}").  Pass just the sessionRef
                      to retrieve the overall session status instead.
    """
    settings = KSeFSettings()
    manager = KSeFLifecycleManager(settings)
    return await manager.get_document_status(reference_number)


async def search_ksef_invoices(
    date_from: str,
    date_to: str,
    subject_type: str = "Subject1",
) -> list[dict[str, Any]]:
    """Query invoices stored in KSeF for a date range.

    Parameters
    ----------
    date_from:    Start date in YYYY-MM-DD format.
    date_to:      End date in YYYY-MM-DD format.
    subject_type: 'Subject1' (seller), 'Subject2' (buyer), 'Subject3' (third party),
                  or 'SubjectAuthorized' (authorised representative). Case-insensitive;
                  normalized to the KSeF v2 PascalCase enum before submission.
    """
    settings = KSeFSettings()
    manager = KSeFLifecycleManager(settings)
    return await manager.search_documents(
        {"date_from": date_from, "date_to": date_to, "subject_type": subject_type}
    )


# ---------------------------------------------------------------------------
# Party / tax-ID validation tools
# ---------------------------------------------------------------------------


async def validate_polish_nip(nip: str) -> dict[str, Any]:
    """Validate a Polish NIP (tax identification number).

    Applies the official 10-digit checksum algorithm.
    Accepts NIP with or without dashes/spaces.

    Returns {'valid': bool, 'nip': str, 'normalized': str}.
    """
    import re

    normalized = re.sub(r"[\s\-]", "", nip)
    valid = validate_nip(nip)
    return {
        "valid": valid,
        "nip": nip,
        "normalized": normalized,
        "message": "NIP is valid." if valid else "NIP failed checksum validation.",
    }


async def validate_polish_regon(regon: str) -> dict[str, Any]:
    """Validate a Polish REGON (business registry number — 9 or 14 digits).

    Returns {'valid': bool, 'regon': str, 'length': int}.
    """
    import re

    normalized = re.sub(r"\s", "", regon)
    valid = validate_regon(regon)
    return {
        "valid": valid,
        "regon": regon,
        "normalized": normalized,
        "length": len(normalized),
        "message": "REGON is valid." if valid else "REGON failed checksum validation.",
    }


# ---------------------------------------------------------------------------
# Peppol / EN 16931 tool
# ---------------------------------------------------------------------------


async def generate_peppol_invoice(invoice: KSeFInvoice) -> str:
    """Generate a Peppol BIS Billing 3.0 / EN 16931 UBL 2.1 XML invoice.

    Use this for cross-border B2B invoicing via the Peppol network.
    For domestic Polish invoicing, use generate_fa3_invoice instead.
    """
    return await _peppol_generator.generate(invoice)


async def validate_peppol_invoice(xml_content: str) -> DocumentValidationResult:
    """Validate a Peppol BIS 3.0 / EN 16931 UBL 2.1 XML invoice.

    Checks the CEN EN16931 base rules only (structural + arithmetic/totals,
    ~50 BR-* rules) via mcp-einvoicing-core's bundled Schematron validator.
    Does NOT check the Peppol-specific overlay (profile/process ID
    registration, EndpointID scheme, narrowed code lists) — the result's
    metadata.scope is "en16931-base-only", and a warning is included. This is
    not a full Peppol BIS3 conformance check; a document that passes may
    still be rejected by a real Peppol Access Point. See
    context-library/decisions/peppol-schematron-artifact.md for why.

    Call this after generate_peppol_invoice to check the generated output.
    Returns a DocumentValidationResult with errors and warnings.
    """
    return await _peppol_validator.validate(xml_content)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def _register_pl_tools(mcp: Any) -> None:
    """Register all Polish e-invoicing tools onto the shared FastMCP instance."""
    mcp.tool()(generate_fa2_invoice)
    mcp.tool()(generate_fa3_invoice)
    mcp.tool()(validate_fa2_invoice)
    mcp.tool()(validate_fa3_invoice)
    mcp.tool()(parse_fa2_invoice)
    mcp.tool()(submit_invoice_to_ksef)
    mcp.tool()(get_ksef_invoice_status)
    mcp.tool()(search_ksef_invoices)
    mcp.tool()(validate_polish_nip)
    mcp.tool()(validate_polish_regon)
    mcp.tool()(generate_peppol_invoice)
    mcp.tool()(validate_peppol_invoice)


mcp = EInvoicingMCPServer(
    "mcp-ksef-pl",
    instructions=(
        "MCP server for Polish electronic invoicing.\n"
        "Supports KSeF FA(2) (legacy, read-only), FA(3) (mandatory for KSeF API v2 submissions, "
        "reconciled against the production API through v2.1.1), "
        "and Peppol BIS 3.0 / EN 16931 UBL.\n"
        "Standard KSeF workflow: generate_fa3_invoice"
        " → validate_fa3_invoice → submit_invoice_to_ksef.\n"
        "Use generate_fa2_invoice and validate_fa2_invoice only for legacy document handling.\n"
        "Use generate_peppol_invoice for cross-border Peppol invoicing, then "
        "validate_peppol_invoice (EN16931 base rules only — not full Peppol "
        "BIS3 overlay conformance; see the tool's own docstring). "
        "peppol_lookup_participant and related Peppol network tools accept a bare "
        "Polish NIP (normalized to Peppol scheme 9945) or a full participant ID.\n"
        "Note: only interactive online sessions (/sessions/online) are supported; "
        "batch submission (/api/batch/) is not yet implemented."
    ),
)
mcp.register_plugin(_register_pl_tools, "pl")
mcp.register_plugin(lambda m: register_peppol_tools(m, id_adapter=_pl_id_adapter), "peppol")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
