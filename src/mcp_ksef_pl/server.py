"""MCP server entry-point for mcp-ksef-pl.

Exposes tools for generating, validating, parsing, submitting, and querying
Polish KSeF (FA(2)) and Peppol BIS 3.0 / EN 16931 electronic invoices.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from mcp_einvoicing_core import (
    DocumentValidationResult,
    InvoiceDocument,
)
from mcp_einvoicing_core.logging_utils import get_logger, setup_logging

from .config import KSeFSettings
from .generator import FA2Generator, FA3Generator
from .lifecycle import KSeFLifecycleManager
from .parser import FA2Parser
from .party_validator import PolishPartyValidator, validate_nip, validate_regon
from .peppol import PeppolUBLGenerator
from .validator import FA2Validator

setup_logging()
logger = get_logger(__name__)

mcp = FastMCP(
    name="mcp-ksef-pl",
    instructions=(
        "MCP server for Polish electronic invoicing.\n"
        "Supports KSeF FA(2) (national format) and Peppol BIS 3.0 / EN 16931 UBL.\n"
        "Use generate_fa2_invoice → validate_fa2_invoice → submit_invoice_to_ksef for the "
        "standard KSeF workflow. Use generate_peppol_invoice for cross-border Peppol invoicing."
    ),
)

_fa2_generator = FA2Generator()
_fa3_generator = FA3Generator()
_fa2_validator = FA2Validator()
_fa2_parser = FA2Parser()
_peppol_generator = PeppolUBLGenerator()
_party_validator = PolishPartyValidator()


# ---------------------------------------------------------------------------
# FA(2) tools
# ---------------------------------------------------------------------------


@mcp.tool
async def generate_fa2_invoice(invoice: InvoiceDocument) -> str:
    """Generate a KSeF-compliant FA(2) XML invoice from structured invoice data.

    Returns the FA(2) XML string ready for submission to KSeF.
    The seller's tax_id must be a Polish NIP (10 digits).
    """
    return await _fa2_generator.generate(invoice)


@mcp.tool
async def generate_fa3_invoice(invoice: InvoiceDocument) -> str:
    """Generate a KSeF-compliant FA(3) XML invoice from structured invoice data.

    FA(3) is required for all new invoice submissions via KSeF API v2.
    Use this tool — not generate_fa2_invoice — before calling submit_invoice_to_ksef.

    The seller's tax_id must be a Polish NIP (10 digits).
    The buyer's tax_id may be a Polish NIP, a EU VAT number (set alt_tax_id),
    or absent (leave tax_id.identifier empty to emit <BrakID>).

    Returns the FA(3) XML string ready for submit_invoice_to_ksef.
    """
    return await _fa3_generator.generate(invoice)


@mcp.tool
async def validate_fa2_invoice(xml_content: str) -> DocumentValidationResult:
    """Validate a KSeF FA(2) XML invoice.

    Runs XSD validation (when the official schema is present) and Polish
    business-rule checks.  Returns a DocumentValidationResult with errors and warnings.
    """
    return await _fa2_validator.validate(xml_content)


@mcp.tool
async def parse_fa2_invoice(xml_content: str) -> dict[str, Any]:
    """Parse a KSeF FA(2) XML invoice into a structured dictionary.

    Returns a nested dict with 'header', 'seller', 'buyer', 'invoice', and 'lines' keys.
    """
    return await _fa2_parser.parse(xml_content)


# ---------------------------------------------------------------------------
# KSeF lifecycle tools
# ---------------------------------------------------------------------------


@mcp.tool
async def submit_invoice_to_ksef(
    xml_content: str,
    session_token: str = "",
) -> dict[str, Any]:
    """Submit a FA(3) XML invoice to the KSeF platform (API v2).

    KSeF API v2 requires FA(3) format for submission.  Use generate_fa2_invoice
    only for validation or parsing; it produces FA(2) XML which KSeF v2 does not
    accept.  FA(3) generation is tracked in roadmap-2026.md.

    Parameters
    ----------
    xml_content:   FA(3) invoice XML string to submit.
    session_token: KSeF v2 AccessToken (overrides KSEF_SESSION_TOKEN env var).
                   Obtain via the challenge → authenticate → redeem flow:
                   https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md

    Returns a dict with:
      session_reference  — KSeF session reference number
      invoice_reference  — per-invoice reference number
      reference_number   — "{sessionRef}:{invoiceRef}" for get_ksef_invoice_status
      status             — "submitted"
    """
    settings = KSeFSettings()
    manager = KSeFLifecycleManager(settings)
    metadata: dict[str, Any] = {}
    if session_token:
        metadata["session_token"] = session_token

    compound_ref = await manager.submit_document(xml_content, metadata)
    session_ref, invoice_ref = compound_ref.split(":", 1)
    return {
        "session_reference": session_ref,
        "invoice_reference": invoice_ref,
        "reference_number": compound_ref,
        "status": "submitted",
    }


@mcp.tool
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


@mcp.tool
async def search_ksef_invoices(
    date_from: str,
    date_to: str,
    subject_type: str = "subject1",
) -> list[dict[str, Any]]:
    """Query invoices stored in KSeF for a date range.

    Parameters
    ----------
    date_from:    Start date in YYYY-MM-DD format.
    date_to:      End date in YYYY-MM-DD format.
    subject_type: 'subject1' (seller), 'subject2' (buyer), or 'subject3' (third party).
    """
    settings = KSeFSettings()
    manager = KSeFLifecycleManager(settings)
    return await manager.search_documents(
        {"date_from": date_from, "date_to": date_to, "subject_type": subject_type}
    )


# ---------------------------------------------------------------------------
# Party / tax-ID validation tools
# ---------------------------------------------------------------------------


@mcp.tool
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


@mcp.tool
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


@mcp.tool
async def generate_peppol_invoice(invoice: InvoiceDocument) -> str:
    """Generate a Peppol BIS Billing 3.0 / EN 16931 UBL 2.1 XML invoice.

    Use this for cross-border B2B invoicing via the Peppol network.
    For domestic Polish invoicing, use generate_fa2_invoice instead.
    """
    return await _peppol_generator.generate(invoice)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
