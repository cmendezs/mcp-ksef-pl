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
    get_logger,
    setup_logging,
)

from .config import KSeFSettings
from .generator import FA2Generator
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
    terminate_after: bool = True,
) -> dict[str, Any]:
    """Submit a FA(2) XML invoice to the KSeF platform.

    Parameters
    ----------
    xml_content:     FA(2) XML string to submit.
    session_token:   KSeF session token (overrides KSEF_SESSION_TOKEN env var).
                     Obtain this via the KSeF auth challenge-response flow.
    terminate_after: Terminate the KSeF session after submission (default True).

    Returns a dict with 'reference_number' and platform response details.
    """
    settings = KSeFSettings()
    manager = KSeFLifecycleManager(settings)
    metadata: dict[str, Any] = {"terminate_after": terminate_after}
    if session_token:
        metadata["session_token"] = session_token

    reference = await manager.submit_document(xml_content, metadata)
    return {"reference_number": reference, "status": "submitted"}


@mcp.tool
async def get_ksef_invoice_status(reference_number: str) -> dict[str, Any]:
    """Retrieve the processing status of a submitted KSeF invoice.

    Parameters
    ----------
    reference_number: The elementReferenceNumber returned by submit_invoice_to_ksef.
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
