"""Pre-publish audit: verify mcp-ksef-pl coherence against mcp-einvoicing-core.

Run standalone (from the workspace root):
    uv run python mcp-ksef-pl/audit/audit_vs_core.py
    uv run python mcp-ksef-pl/audit/audit_vs_core.py --output mcp-ksef-pl/audit/report.json
    uv run python mcp-ksef-pl/audit/audit_vs_core.py --fail-on blocking
    uv run python mcp-ksef-pl/audit/audit_vs_core.py --fail-on warnings

Exit codes:
    0  All checks passed
    1  Warnings only (non-blocking)
    2  Blocking failures found

This script is designed to be importable with no side effects; all execution
is guarded by `if __name__ == "__main__"`.

CHECK 1 and CHECK 4 are delegated to mcp_einvoicing_core.audit.
CHECK 2 (tool registry), CHECK 3 (InvoiceDocument field coverage), and CHECK 5
(KSeF-specific structural) are implemented here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp_einvoicing_core.audit import (
    SEVERITY_BLOCKING,
    SEVERITY_OK,
    SEVERITY_WARNING,
    AuditReport,
    CheckFinding,
    CheckResult,
    _try_import,
    make_report,
    parse_audit_args,
    render_summary_table,
    run_check_core_coverage,
    run_check_version_compatibility,
)

# ---------------------------------------------------------------------------
# CHECK 1 configuration — country-specific constants
# ---------------------------------------------------------------------------

# KSeFInvoice(EN16931Invoice) is the primary data model for KSeF FA(2)/FA(3).
# Polish VAT invoices are semantically EN 16931 compliant; the KSeF XML schema is a
# national serialisation format that generators map to from the EN 16931 data model.
# The FA(2)/FA(3) generators in generator.py still accept InvoiceDocument during the
# migration period; that is tracked in the roadmap under "KSeF generator migration".
_IS_EN16931_FAMILY: bool = True
_PRIMARY_INVOICE_CLASS: tuple[str, str] = ("mcp_ksef_pl.models", "KSeFInvoice")

_INTENTIONAL_OVERRIDES: dict[str, set[str]] = {
    # KSeF uses standalone FastMCP; base ABC classes are not subclassed directly.
    "mcp_einvoicing_core.base_server": {
        "BaseDocumentGenerator",
        "BaseDocumentParser",
        "BaseDocumentValidator",
        "BasePartyValidator",
        "EInvoicingMCPServer",
    },
    # XAdES signing is ES-specific. KSeF uses AES-256-CBC + RSA-OAEP at the
    # transport layer (handled in _encryption.py), not document-level signing.
    "mcp_einvoicing_core.digital_signature": {
        "BaseDocumentSigner",
        "XAdESEPESSigner",
        "XAdESSignerConfig",
        # OVERRIDE-REASON: XMLDSigSigner/XMLDSigSignerConfig (core v1.4.0) is
        # the BR NF-e plain enveloped XML-DSig signer; not applicable to
        # KSeF FA(3)/FA(2), which use XAdES-EPES / Peppol BIS 3.0 signing
        "XMLDSigSigner",
        "XMLDSigSignerConfig",
    },
    # EN16931 classes are used via KSeFInvoice(EN16931Invoice) and KSeFParty(EN16931Party).
    # The specific sub-classes (EN16931LineItem, EN16931PaymentMeans) are accessed through
    # the EN16931Invoice base; the generators migrate to these field names incrementally.
    "mcp_einvoicing_core.en16931": {
        "EN16931Address",
        "EN16931AllowanceCharge",
        "EN16931LineItem",
        "EN16931PaymentMeans",
        "EN16931Tax",
    },
    # PL uses PlatformError and DocumentGenerationError; the others are not raised.
    "mcp_einvoicing_core.exceptions": {
        "AuthenticationError",
        "PartyValidationError",
        "SchematronValidationError",
    },
    # KSeF uses BEARER_TOKEN session auth; OAuth2 client_credentials is not used.
    "mcp_einvoicing_core.http_client": {
        "OAuthConfig",
        "TokenCache",
    },
    # PaymentTerms — not used in FA(2)/FA(3) invoice structure.
    "mcp_einvoicing_core.models": {
        "PaymentTerms",
    },
    # PDF/A-3 embedding is not required for KSeF XML invoices.
    "mcp_einvoicing_core.pdf": {
        "PDFEmbedder",
    },
    # QR codes are not required by the KSeF specification.
    "mcp_einvoicing_core.qr": {
        "generate_qr_png_base64",
    },
    # KSeF uses XSD + business-rule validation, not Schematron/SVRL.
    "mcp_einvoicing_core.schematron": {
        "BaseStructuredValidator",
        "SchematronValidator",
        "ValidationMessage",
        "ValidationResult",
    },
    # KSeF artefacts are not managed through the download_rules framework.
    "mcp_einvoicing_core.download_rules": {
        "DownloadSpec",
        "download_artefacts",
    },
    # xml_element/xml_optional/validate_iban: not used in KSeF XML generation.
    "mcp_einvoicing_core.xml_utils": {
        "validate_iban",
        "xml_element",
        "xml_optional",
    },
}

_PKG_MODULES: list[str] = [
    "mcp_ksef_pl",
    "mcp_ksef_pl.config",
    "mcp_ksef_pl.generator",
    "mcp_ksef_pl.validator",
    "mcp_ksef_pl.parser",
    "mcp_ksef_pl.lifecycle",
    "mcp_ksef_pl.party_validator",
    "mcp_ksef_pl.peppol",
    "mcp_ksef_pl.peppol.generator",
]

_PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


# ---------------------------------------------------------------------------
# CHECK 2 — Tool registry completeness
# ---------------------------------------------------------------------------

_REQUIRED_TOOL_CATEGORIES: dict[str, str] = {
    "generate_fa2_invoice":    "Generate KSeF FA(2) XML from invoice data",
    "generate_fa3_invoice":    "Generate KSeF FA(3) XML from invoice data (mandatory for v2)",
    "validate_fa2_invoice":    "XSD + business-rule validation of FA(2)",
    "validate_fa3_invoice":    "XSD + business-rule validation of FA(3) — PL-6.2",
    "parse_fa2_invoice":       "Parse FA(2) XML to structured dict",
    "submit_invoice_to_ksef":  "Submit to KSeF platform, return reference number",
    "get_ksef_invoice_status": "Poll processing status by reference number",
    "search_ksef_invoices":    "Query KSeF by date range and subject type",
    "validate_polish_nip":     "Validate 10-digit Polish NIP (checksum)",
    "validate_polish_regon":   "Validate 9- or 14-digit Polish REGON (checksum)",
    "generate_peppol_invoice": "Generate Peppol BIS 3.0 / EN 16931 UBL 2.1",
}


def _collect_registered_tools() -> set[str]:
    registered: set[str] = set()
    mod, _ = _try_import("mcp_ksef_pl.server")
    if mod is None:
        return registered
    for tool_name in _REQUIRED_TOOL_CATEGORIES:
        if hasattr(mod, tool_name) and callable(getattr(mod, tool_name)):
            registered.add(tool_name)
    return registered


def run_check_2() -> CheckResult:
    """CHECK 2 — Tool registry completeness."""
    result = CheckResult(check_id="CHECK_2", name="Tool registry completeness")
    registered = _collect_registered_tools()

    for tool_name, description in _REQUIRED_TOOL_CATEGORIES.items():
        tag = "[OK]" if tool_name in registered else "[MISSING_TOOL]"
        sev = SEVERITY_OK if tool_name in registered else SEVERITY_BLOCKING
        result.findings.append(CheckFinding(
            check_id="CHECK_2", tag=tag, severity=sev,
            symbol=tool_name,
            message=(
                f"Tool '{tool_name}' is present. ({description})"
                if tool_name in registered
                else (
                    f"Required tool '{tool_name}' ({description}) not found in "
                    "mcp_ksef_pl.server. Ensure it is decorated with @mcp.tool."
                )
            ),
        ))

    for tool_name in sorted(registered - set(_REQUIRED_TOOL_CATEGORIES)):
        result.findings.append(CheckFinding(
            check_id="CHECK_2", tag="[EXTRA]", severity=SEVERITY_OK,
            symbol=tool_name,
            message=f"Tool '{tool_name}' is present but not in the required spec.",
        ))

    return result


# ---------------------------------------------------------------------------
# CHECK 3 — Core model field availability (InvoiceDocument)
# ---------------------------------------------------------------------------

_REQUIRED_INVOICE_DOCUMENT_FIELDS: dict[str, str] = {
    "number":      "BT-1  — Invoice number",
    "date":        "BT-2  — Invoice issue date",
    "currency":    "BT-5  — Invoice currency",
    "seller":      "BG-4  — Seller party",
    "buyer":       "BG-7  — Buyer party",
    "lines":       "BG-25 — Invoice lines",
    "vat_summary": "BG-23 — VAT breakdown",
}


def run_check_3() -> CheckResult:
    """CHECK 3 — Core model field availability (InvoiceDocument field coverage)."""
    result = CheckResult(check_id="CHECK_3", name="Core model field availability")

    core_mod, err = _try_import("mcp_einvoicing_core")
    if core_mod is None:
        result.skipped = True
        result.skip_reason = f"Could not import mcp_einvoicing_core: {err}"
        return result

    invoice_cls = getattr(core_mod, "InvoiceDocument", None)
    if invoice_cls is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_3", tag="[MISSING]", severity=SEVERITY_BLOCKING,
            symbol="mcp_einvoicing_core.InvoiceDocument",
            message="InvoiceDocument not found in mcp_einvoicing_core — core may be outdated.",
        ))
        return result

    result.findings.append(CheckFinding(
        check_id="CHECK_3", tag="[OK]", severity=SEVERITY_OK,
        symbol="mcp_einvoicing_core.InvoiceDocument",
        message="InvoiceDocument is available from core.",
    ))

    model_fields: set[str] = set()
    if hasattr(invoice_cls, "model_fields"):
        model_fields = set(invoice_cls.model_fields.keys())

    if not model_fields:
        result.findings.append(CheckFinding(
            check_id="CHECK_3", tag="[SKIP]", severity=SEVERITY_WARNING,
            symbol="InvoiceDocument.model_fields",
            message="Could not introspect InvoiceDocument.model_fields — skipping field check.",
        ))
        return result

    for field_name, description in _REQUIRED_INVOICE_DOCUMENT_FIELDS.items():
        tag = "[OK]" if field_name in model_fields else "[FIELD_MISSING]"
        sev = SEVERITY_OK if field_name in model_fields else SEVERITY_WARNING
        result.findings.append(CheckFinding(
            check_id="CHECK_3", tag=tag, severity=sev,
            symbol=f"InvoiceDocument.{field_name}",
            message=(
                f"Required field present. {description}"
                if field_name in model_fields
                else (
                    f"Field '{field_name}' ({description}) not found in "
                    "InvoiceDocument.model_fields. "
                    "Verify the FA(2) generator will not fail at runtime."
                )
            ),
        ))

    return result


# ---------------------------------------------------------------------------
# CHECK 5 — KSeF-specific structural checks
# ---------------------------------------------------------------------------

def run_check_5() -> CheckResult:
    """CHECK 5 — KSeF-specific structural and completeness checks."""
    result = CheckResult(check_id="CHECK_5", name="KSeF-specific structural checks")

    # 5a: server module exports main + mcp
    server_mod, err = _try_import("mcp_ksef_pl.server")
    if server_mod is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_BLOCKING,
            symbol="mcp_ksef_pl.server",
            message=f"Could not import server module: {err}",
        ))
    else:
        for attr in ("main", "mcp"):
            tag = "[OK]" if hasattr(server_mod, attr) else "[MISSING]"
            sev = SEVERITY_OK if hasattr(server_mod, attr) else SEVERITY_BLOCKING
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag=tag, severity=sev,
                symbol=f"server.{attr}",
                message=(
                    f"server.{attr} is present."
                    if hasattr(server_mod, attr)
                    else f"server.{attr} is missing — required for MCP server operation."
                ),
            ))

        # 5b: mcp must be a FastMCP instance
        mcp_obj = getattr(server_mod, "mcp", None)
        if mcp_obj is not None:
            mcp_type = type(mcp_obj).__name__
            tag = "[OK]" if mcp_type == "FastMCP" else "[UNEXPECTED_TYPE]"
            sev = SEVERITY_OK if mcp_type == "FastMCP" else SEVERITY_WARNING
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag=tag, severity=sev,
                symbol="server.mcp",
                message=(
                    "server.mcp is a FastMCP instance."
                    if mcp_type == "FastMCP"
                    else (
                        f"server.mcp is {mcp_type!r}, expected FastMCP. "
                        "Verify tool registration is using FastMCP decorators."
                    )
                ),
            ))

    # 5c: KSeFEnvironment enum exists in config
    config_mod, err = _try_import("mcp_ksef_pl.config")
    if config_mod is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_BLOCKING,
            symbol="mcp_ksef_pl.config",
            message=f"Could not import config module: {err}",
        ))
    else:
        env_cls = getattr(config_mod, "KSeFEnvironment", None)
        if env_cls is None:
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_BLOCKING,
                symbol="KSeFEnvironment",
                message="KSeFEnvironment enum not found in mcp_ksef_pl.config.",
            ))
        else:
            required_envs = {"PRODUCTION", "TEST"}
            actual_envs = {e.name for e in env_cls}
            for env in sorted(required_envs):
                tag = "[OK]" if env in actual_envs else "[MISSING_ENV]"
                sev = SEVERITY_OK if env in actual_envs else SEVERITY_BLOCKING
                result.findings.append(CheckFinding(
                    check_id="CHECK_5", tag=tag, severity=sev,
                    symbol=f"KSeFEnvironment.{env}",
                    message=(
                        "Environment variant defined."
                        if env in actual_envs
                        else f"Required KSeF environment '{env}' missing from KSeFEnvironment enum."
                    ),
                ))

    # 5d: XSD schema directory presence (WARNING only)
    schemas_dir = (
        Path(__file__).parent.parent / "src" / "mcp_ksef_pl" / "schemas"
    )
    if schemas_dir.exists():
        xsd_files = list(schemas_dir.glob("*.xsd"))
        if xsd_files:
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag="[OK]", severity=SEVERITY_OK,
                symbol="src/mcp_ksef_pl/schemas/",
                message=(
                    f"XSD schema directory found with {len(xsd_files)} file(s): "
                    f"{', '.join(f.name for f in xsd_files)}"
                ),
            ))
        else:
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag="[MISSING_SCHEMA]", severity=SEVERITY_WARNING,
                symbol="src/mcp_ksef_pl/schemas/",
                message=(
                    "schemas/ directory exists but contains no .xsd files. "
                    "FA(2) XSD validation will be skipped at runtime. "
                    "Download FA_VAT_v1-0E.xsd from the Polish Ministry of Finance "
                    "and place it in src/mcp_ksef_pl/schemas/."
                ),
            ))
    else:
        result.findings.append(CheckFinding(
            check_id="CHECK_5", tag="[MISSING_SCHEMA]", severity=SEVERITY_WARNING,
            symbol="src/mcp_ksef_pl/schemas/",
            message=(
                "schemas/ directory not found. FA(2) XSD validation will be skipped "
                "at runtime. Download FA_VAT_v1-0E.xsd from the Polish Ministry of "
                "Finance and place it in src/mcp_ksef_pl/schemas/."
            ),
        ))

    # 5e: validator XSDs must ship inside the wheel (PL-6.3). The FA(2)/FA(3)
    # validators load their XSDs via a path that resolves in the source tree but
    # points outside the packaged tree. The wheel is built with
    # packages = ["src/mcp_ksef_pl"] and no force-include for specs/, so once
    # installed get_schema_path() returns None and XSD validation is silently
    # skipped — masking any schema drift in the generators. This check flags the
    # gap in the source tree by verifying the resolved XSD lives under the package
    # dir OR that pyproject force-includes it. WARNING (not blocking) so the gate
    # still passes while the packaging fix is tracked on the roadmap.
    pkg_src_dir = (Path(__file__).parent.parent / "src" / "mcp_ksef_pl").resolve()
    pyproject_text = _PYPROJECT.read_text(encoding="utf-8") if _PYPROJECT.exists() else ""
    force_includes_specs = "force-include" in pyproject_text and "specs" in pyproject_text

    validator_mod, verr = _try_import("mcp_ksef_pl.validator")
    if validator_mod is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_WARNING,
            symbol="mcp_ksef_pl.validator",
            message=f"Could not import validator module for schema-path check: {verr}",
        ))
    else:
        for cls_name in ("FA2Validator", "FA3Validator"):
            cls = getattr(validator_mod, cls_name, None)
            if cls is None:
                continue
            try:
                raw_path = cls().get_schema_path()
            except Exception:  # noqa: BLE001 - defensive: report, do not crash the gate
                raw_path = None
            schema_path = Path(raw_path).resolve() if raw_path else None
            under_package = bool(
                schema_path and pkg_src_dir in schema_path.parents
            )
            if raw_path is None:
                result.findings.append(CheckFinding(
                    check_id="CHECK_5", tag="[XSD_UNREACHABLE]", severity=SEVERITY_WARNING,
                    symbol=f"{cls_name}.get_schema_path",
                    message=(
                        f"{cls_name}.get_schema_path() returned None — XSD validation is "
                        "skipped (PL-6.3). Ship the XSD inside mcp_ksef_pl and load via "
                        "importlib.resources."
                    ),
                ))
            elif under_package or force_includes_specs:
                result.findings.append(CheckFinding(
                    check_id="CHECK_5", tag="[OK]", severity=SEVERITY_OK,
                    symbol=f"{cls_name}.get_schema_path",
                    message=f"XSD is packaged and reachable for XSD validation: {raw_path}",
                ))
            else:
                result.findings.append(CheckFinding(
                    check_id="CHECK_5", tag="[XSD_UNPACKAGED]", severity=SEVERITY_WARNING,
                    symbol=f"{cls_name}.get_schema_path",
                    message=(
                        f"{cls_name} loads its XSD from {raw_path}, which is outside the "
                        "packaged tree (src/mcp_ksef_pl/) and pyproject has no force-include "
                        "for specs/. The XSD will not ship in the wheel, so XSD validation "
                        "is silently skipped once installed (PL-6.3). Move the XSDs under "
                        "src/mcp_ksef_pl/ and load via importlib.resources, or force-include "
                        "specs/ in [tool.hatch.build.targets.wheel]."
                    ),
                ))

    return result


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CHECK 6 — Parallel-implementation detector (Phase 0a.2)
# ---------------------------------------------------------------------------

_CORE_CAPABILITIES: list[tuple[str, str, list[str]]] = [
    ("cii_ubl_conversion", "mcp_einvoicing_core.convert", [
        "convert_wire_format",
    ]),
    ("peppol_participant_lookup", "mcp_einvoicing_core.peppol", [
        "PeppolSMPClient",
    ]),
    ("en16931_cii_parsing", "mcp_einvoicing_core.wire_formats", [
        "EN16931CIIParser", "EN16931CIISerializer",
    ]),
    ("en16931_ubl_parsing", "mcp_einvoicing_core.wire_formats", [
        "EN16931UBLParser", "EN16931UBLSerializer",
    ]),
    ("schematron_validation", "mcp_einvoicing_core.schematron", [
        "SchematronValidator",
    ]),
    ("xades_xmldsig_signing", "mcp_einvoicing_core.digital_signature", [
        "XAdESEPESSigner", "XMLDSigSigner",
    ]),
    ("http_client", "mcp_einvoicing_core.http_client", [
        "BaseEInvoicingClient",
    ]),
    ("routing_identifier_validation", "mcp_einvoicing_core.routing", [
        "RoutingIdentifier",
    ]),
    ("peppol_as4_transport", "mcp_einvoicing_core.peppol.transport", [
        "AS4MessageEnvelope", "AS4TransportClient", "PeppolTransmitter",
    ]),
]

_INTENTIONAL_PARALLEL_IMPLEMENTATIONS: dict[tuple[str, str], str] = {}


def run_check_6() -> CheckResult:
    """CHECK 6 — Parallel-implementation scan."""
    import ast

    result = CheckResult(check_id="CHECK_6", name="Parallel-implementation detector")

    pkg_root = Path(__file__).parent.parent / "src" / "mcp_ksef_pl"
    if not pkg_root.is_dir():
        result.findings.append(CheckFinding(
            check_id="CHECK_6", tag="[SKIP]", severity=SEVERITY_OK,
            symbol="mcp_ksef_pl",
            message="Package source directory not found; skipping parallel-implementation scan.",
        ))
        return result

    defined_names: dict[str, str] = {}
    for py_file in pkg_root.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_names[node.name] = str(py_file.relative_to(pkg_root.parent.parent))

    found_any = False
    for cap_tag, core_module, symbols in _CORE_CAPABILITIES:
        for symbol in symbols:
            if symbol not in defined_names:
                continue

            override_key = (cap_tag, symbol)
            if override_key in _INTENTIONAL_PARALLEL_IMPLEMENTATIONS:
                result.findings.append(CheckFinding(
                    check_id="CHECK_6", tag="[OVERRIDE]", severity=SEVERITY_OK,
                    symbol=symbol,
                    message=(
                        f"Parallel implementation of {symbol} ({cap_tag}) in "
                        f"{defined_names[symbol]} is intentional: "
                        f"{_INTENTIONAL_PARALLEL_IMPLEMENTATIONS[override_key]}"
                    ),
                ))
                continue

            found_any = True
            result.findings.append(CheckFinding(
                check_id="CHECK_6", tag="[PARALLEL]", severity=SEVERITY_WARNING,
                symbol=symbol,
                message=(
                    f"Country package defines {symbol!r} in {defined_names[symbol]}, "
                    f"which mirrors core capability {cap_tag!r} from {core_module}. "
                    "Delegate to the core symbol or register in "
                    "_INTENTIONAL_PARALLEL_IMPLEMENTATIONS with a justification."
                ),
            ))

    if not found_any and not result.findings:
        result.findings.append(CheckFinding(
            check_id="CHECK_6", tag="[OK]", severity=SEVERITY_OK,
            symbol="*",
            message="No parallel implementations of core capabilities detected.",
        ))

    return result


def run_audit() -> AuditReport:
    """Execute all checks and return the aggregated AuditReport. No side effects."""
    report = make_report("mcp-ksef-pl", _PYPROJECT)

    report.checks.append(run_check_core_coverage(
        package_name="mcp-ksef-pl",
        package_modules=_PKG_MODULES,
        intentional_overrides=_INTENTIONAL_OVERRIDES,
        is_en16931_family=_IS_EN16931_FAMILY,
        primary_invoice_class=_PRIMARY_INVOICE_CLASS,
    ))
    report.checks.append(run_check_2())
    report.checks.append(run_check_3())
    report.checks.append(run_check_version_compatibility(
        package_name="mcp-ksef-pl",
        pyproject_path=_PYPROJECT,
    ))
    report.checks.append(run_check_5())
    report.checks.append(run_check_6())

    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_audit_args(
        "Pre-publish audit: mcp-ksef-pl vs mcp-einvoicing-core", argv
    )
    report = run_audit()

    output_path = Path(args.output) if args.output else Path("audit/report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    if not args.quiet:
        print(render_summary_table(report))
        print(f"\nJSON report written to: {output_path}")

    if args.fail_on == "never":
        return 0
    if args.fail_on == "warnings":
        return min(report.exit_code, 2)
    return 2 if report.total_blocking > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
