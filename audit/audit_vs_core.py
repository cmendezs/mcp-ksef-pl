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

[NEED: update CHECK 1 _INTENTIONAL_OVERRIDES once mcp-einvoicing-core public API is finalised]
[NEED: update CHECK 4 to use packaging.version for full PEP 440 specifier support]
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import inspect
import json
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

SEVERITY_BLOCKING = "BLOCKING"
SEVERITY_WARNING = "WARNING"
SEVERITY_OK = "OK"
SEVERITY_SKIP = "SKIP"


@dataclass
class CheckFinding:
    check_id: str
    tag: str
    severity: str
    symbol: str
    message: str


@dataclass
class CheckResult:
    check_id: str
    name: str
    findings: list[CheckFinding] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    @property
    def blocking_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_BLOCKING)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_WARNING)

    @property
    def passed(self) -> bool:
        return self.blocking_count == 0


@dataclass
class AuditReport:
    generated_at: str
    pkg_version: str
    core_version: str | None
    core_version_compatible: bool
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def total_blocking(self) -> int:
        return sum(c.blocking_count for c in self.checks)

    @property
    def total_warnings(self) -> int:
        return sum(c.warning_count for c in self.checks)

    @property
    def exit_code(self) -> int:
        if self.total_blocking > 0:
            return 2
        if self.total_warnings > 0:
            return 1
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "pkg_version": self.pkg_version,
            "core_version": self.core_version,
            "core_version_compatible": self.core_version_compatible,
            "exit_code": self.exit_code,
            "total_blocking": self.total_blocking,
            "total_warnings": self.total_warnings,
            "checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "passed": c.passed,
                    "skipped": c.skipped,
                    "skip_reason": c.skip_reason,
                    "blocking_count": c.blocking_count,
                    "warning_count": c.warning_count,
                    "findings": [
                        {
                            "check_id": f.check_id,
                            "tag": f.tag,
                            "severity": f.severity,
                            "symbol": f.symbol,
                            "message": f.message,
                        }
                        for f in c.findings
                    ],
                }
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _try_import(module_path: str) -> tuple[Any | None, str | None]:
    try:
        return importlib.import_module(module_path), None
    except ImportError as exc:
        return None, str(exc)


def _get_public_symbols(module: Any) -> dict[str, Any]:
    if hasattr(module, "__all__"):
        return {name: getattr(module, name) for name in module.__all__ if hasattr(module, name)}
    return {
        name: obj
        for name, obj in inspect.getmembers(module)
        if not name.startswith("_") and not inspect.ismodule(obj)
    }


def _get_installed_version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _parse_version(v: str) -> tuple[int, ...]:
    parts = v.split(".")
    result = []
    for p in parts[:3]:
        try:
            result.append(int(p.split("a")[0].split("b")[0].split("rc")[0]))
        except ValueError:
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return tuple(result)


def _version_in_range(version: str, spec: str) -> bool:
    """
    Naive PEP 440 specifier check for >=X,<Y ranges.
    [NEED: replace with packaging.version for full PEP 440 compliance]
    """
    v = _parse_version(version)
    for part in spec.split(","):
        part = part.strip()
        if part.startswith(">="):
            if v < _parse_version(part[2:].strip()):
                return False
        elif part.startswith("<"):
            if v >= _parse_version(part[1:].strip()):
                return False
        elif part.startswith("~="):
            base = _parse_version(part[2:].strip())
            if len(base) >= 2 and (v < base or v[0] != base[0]):
                return False
    return True


# ---------------------------------------------------------------------------
# CHECK 1 — Core interface coverage
# ---------------------------------------------------------------------------

# Symbols mcp-ksef-pl intentionally overrides rather than importing from core.
# [NEED: populate once mcp-einvoicing-core public API is finalised]
_INTENTIONAL_OVERRIDES: dict[str, set[str]] = {}

_CORE_MODULES_TO_CHECK: list[str] = [
    "mcp_einvoicing_core",
    "mcp_einvoicing_core.models",
    "mcp_einvoicing_core.validators",
    "mcp_einvoicing_core.tools",
]

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


def _collect_pkg_imports() -> set[str]:
    imported: set[str] = set()
    for mod_path in _PKG_MODULES:
        mod, _ = _try_import(mod_path)
        if mod is None:
            continue
        for name, obj in inspect.getmembers(mod):
            if not name.startswith("_"):
                obj_module = getattr(obj, "__module__", "") or ""
                if "mcp_einvoicing_core" in obj_module:
                    imported.add(name)
    return imported


def run_check_1() -> CheckResult:
    """CHECK 1 — Core interface coverage."""
    result = CheckResult(check_id="CHECK_1", name="Core interface coverage")

    if _get_installed_version("mcp-einvoicing-core") is None:
        result.skipped = True
        result.skip_reason = (
            "mcp-einvoicing-core is not installed. "
            "Run: uv sync --all-packages --all-extras"
        )
        result.findings.append(CheckFinding(
            check_id="CHECK_1",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol="mcp-einvoicing-core",
            message="Package not installed — cannot verify core interface coverage.",
        ))
        return result

    pkg_imports = _collect_pkg_imports()

    for mod_path in _CORE_MODULES_TO_CHECK:
        core_mod, err = _try_import(mod_path)
        if core_mod is None:
            result.findings.append(CheckFinding(
                check_id="CHECK_1",
                tag="[SKIP]",
                severity=SEVERITY_WARNING,
                symbol=mod_path,
                message=f"Could not import core module: {err}",
            ))
            continue

        overrides_for_mod = _INTENTIONAL_OVERRIDES.get(mod_path, set())
        symbols = _get_public_symbols(core_mod)

        for sym_name, sym_obj in symbols.items():
            if not (inspect.isclass(sym_obj) or inspect.isfunction(sym_obj)):
                continue

            if sym_name in overrides_for_mod:
                result.findings.append(CheckFinding(
                    check_id="CHECK_1",
                    tag="[OVERRIDE]",
                    severity=SEVERITY_OK,
                    symbol=f"{mod_path}.{sym_name}",
                    message="Intentionally overridden by mcp-ksef-pl.",
                ))
            elif sym_name in pkg_imports:
                result.findings.append(CheckFinding(
                    check_id="CHECK_1",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol=f"{mod_path}.{sym_name}",
                    message="Imported and used.",
                ))
            else:
                result.findings.append(CheckFinding(
                    check_id="CHECK_1",
                    tag="[MISSING]",
                    severity=SEVERITY_WARNING,
                    symbol=f"{mod_path}.{sym_name}",
                    message=(
                        f"Core symbol '{sym_name}' is neither imported by mcp-ksef-pl "
                        "nor marked as an intentional override. "
                        "Add to _INTENTIONAL_OVERRIDES if this is deliberate."
                    ),
                ))

    return result


# ---------------------------------------------------------------------------
# CHECK 2 — Tool registry completeness
# ---------------------------------------------------------------------------

# Tool names as declared in server.json, with a short description.
_REQUIRED_TOOL_CATEGORIES: dict[str, str] = {
    "generate_fa2_invoice":    "Generate KSeF FA(2) XML from invoice data",
    "validate_fa2_invoice":    "XSD + business-rule validation of FA(2)",
    "parse_fa2_invoice":       "Parse FA(2) XML to structured dict",
    "submit_invoice_to_ksef":  "Submit to KSeF platform, return reference number",
    "get_ksef_invoice_status": "Poll processing status by reference number",
    "search_ksef_invoices":    "Query KSeF by date range and subject type",
    "validate_polish_nip":     "Validate 10-digit Polish NIP (checksum)",
    "validate_polish_regon":   "Validate 9- or 14-digit Polish REGON (checksum)",
    "generate_peppol_invoice": "Generate Peppol BIS 3.0 / EN 16931 UBL 2.1",
}


def _collect_registered_tools() -> set[str]:
    """Return tool names registered via @mcp.tool in the server module."""
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
        if tool_name in registered:
            result.findings.append(CheckFinding(
                check_id="CHECK_2",
                tag="[OK]",
                severity=SEVERITY_OK,
                symbol=tool_name,
                message=f"Tool '{tool_name}' is present. ({description})",
            ))
        else:
            result.findings.append(CheckFinding(
                check_id="CHECK_2",
                tag="[MISSING_TOOL]",
                severity=SEVERITY_BLOCKING,
                symbol=tool_name,
                message=(
                    f"Required tool '{tool_name}' ({description}) not found in "
                    "mcp_ksef_pl.server. Ensure it is decorated with @mcp.tool."
                ),
            ))

    extra = registered - set(_REQUIRED_TOOL_CATEGORIES)
    for tool_name in sorted(extra):
        result.findings.append(CheckFinding(
            check_id="CHECK_2",
            tag="[EXTRA]",
            severity=SEVERITY_OK,
            symbol=tool_name,
            message=f"Tool '{tool_name}' is present but not in the required spec.",
        ))

    return result


# ---------------------------------------------------------------------------
# CHECK 3 — Core model availability
# ---------------------------------------------------------------------------

# Fields that the FA(2) generator and parser rely on from InvoiceDocument.
# [NEED: derive from mcp-einvoicing-core BaseInvoice.model_fields once API is stable]
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
    """CHECK 3 — Core model availability (InvoiceDocument field coverage)."""
    result = CheckResult(check_id="CHECK_3", name="Core model field availability")

    core_mod, err = _try_import("mcp_einvoicing_core")
    if core_mod is None:
        result.skipped = True
        result.skip_reason = f"Could not import mcp_einvoicing_core: {err}"
        return result

    invoice_cls = getattr(core_mod, "InvoiceDocument", None)
    if invoice_cls is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_3",
            tag="[MISSING]",
            severity=SEVERITY_BLOCKING,
            symbol="mcp_einvoicing_core.InvoiceDocument",
            message="InvoiceDocument not found in mcp_einvoicing_core — core may be outdated.",
        ))
        return result

    result.findings.append(CheckFinding(
        check_id="CHECK_3",
        tag="[OK]",
        severity=SEVERITY_OK,
        symbol="mcp_einvoicing_core.InvoiceDocument",
        message="InvoiceDocument is available from core.",
    ))

    model_fields: set[str] = set()
    if hasattr(invoice_cls, "model_fields"):
        model_fields = set(invoice_cls.model_fields.keys())

    if not model_fields:
        result.findings.append(CheckFinding(
            check_id="CHECK_3",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol="InvoiceDocument.model_fields",
            message=(
                "Could not introspect InvoiceDocument.model_fields — "
                "skipping field-level coverage check."
            ),
        ))
        return result

    for field_name, description in _REQUIRED_INVOICE_DOCUMENT_FIELDS.items():
        if field_name in model_fields:
            result.findings.append(CheckFinding(
                check_id="CHECK_3",
                tag="[OK]",
                severity=SEVERITY_OK,
                symbol=f"InvoiceDocument.{field_name}",
                message=f"Required field present. {description}",
            ))
        else:
            result.findings.append(CheckFinding(
                check_id="CHECK_3",
                tag="[FIELD_MISSING]",
                severity=SEVERITY_WARNING,
                symbol=f"InvoiceDocument.{field_name}",
                message=(
                    f"Field '{field_name}' ({description}) not found in "
                    "InvoiceDocument.model_fields. "
                    "[Inference] The FA(2) generator may fail at runtime if this field "
                    "is absent from core. Verify against actual generator code."
                ),
            ))

    return result


# ---------------------------------------------------------------------------
# CHECK 4 — Version compatibility
# ---------------------------------------------------------------------------

def _read_core_version_spec_from_pyproject() -> str | None:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    try:
        text = pyproject_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "mcp-einvoicing-core" in line:
                start = line.find("mcp-einvoicing-core")
                fragment = line[start:].strip().strip('",').strip("'")
                spec = fragment.replace("mcp-einvoicing-core", "").strip()
                return spec if spec else None
    except Exception:
        pass
    return None


def run_check_4() -> CheckResult:
    """CHECK 4 — Version compatibility."""
    result = CheckResult(check_id="CHECK_4", name="Version compatibility")

    installed_core = _get_installed_version("mcp-einvoicing-core")
    if installed_core is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_4",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol="mcp-einvoicing-core",
            message="mcp-einvoicing-core not installed — cannot check version compatibility.",
        ))
        return result

    declared_spec = _read_core_version_spec_from_pyproject()
    if declared_spec is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_4",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol="pyproject.toml",
            message=(
                "Could not parse mcp-einvoicing-core version spec from pyproject.toml. "
                "[NEED: ensure pyproject.toml uses standard PEP 440 specifiers]"
            ),
        ))
        return result

    compatible = _version_in_range(installed_core, declared_spec)
    tag = "[OK]" if compatible else "[VERSION_MISMATCH]"
    severity = SEVERITY_OK if compatible else SEVERITY_BLOCKING

    result.findings.append(CheckFinding(
        check_id="CHECK_4",
        tag=tag,
        severity=severity,
        symbol="mcp-einvoicing-core",
        message=(
            f"Installed: {installed_core} | "
            f"Declared range: {declared_spec} | "
            f"Compatible: {compatible}"
        ),
    ))

    return result


# ---------------------------------------------------------------------------
# CHECK 5 — KSeF-specific structural checks
# ---------------------------------------------------------------------------

def run_check_5() -> CheckResult:
    """CHECK 5 — KSeF-specific structural and completeness checks."""
    result = CheckResult(check_id="CHECK_5", name="KSeF-specific structural checks")

    # 5a: server module imports and exports main + mcp
    server_mod, err = _try_import("mcp_ksef_pl.server")
    if server_mod is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_5",
            tag="[MISSING]",
            severity=SEVERITY_BLOCKING,
            symbol="mcp_ksef_pl.server",
            message=f"Could not import server module: {err}",
        ))
    else:
        for attr in ("main", "mcp"):
            if hasattr(server_mod, attr):
                result.findings.append(CheckFinding(
                    check_id="CHECK_5",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol=f"server.{attr}",
                    message=f"server.{attr} is present.",
                ))
            else:
                result.findings.append(CheckFinding(
                    check_id="CHECK_5",
                    tag="[MISSING]",
                    severity=SEVERITY_BLOCKING,
                    symbol=f"server.{attr}",
                    message=f"server.{attr} is missing — required for MCP server operation.",
                ))

        # 5b: mcp must be a FastMCP instance
        mcp_obj = getattr(server_mod, "mcp", None)
        if mcp_obj is not None:
            mcp_type = type(mcp_obj).__name__
            if mcp_type == "FastMCP":
                result.findings.append(CheckFinding(
                    check_id="CHECK_5",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol="server.mcp",
                    message="server.mcp is a FastMCP instance.",
                ))
            else:
                result.findings.append(CheckFinding(
                    check_id="CHECK_5",
                    tag="[UNEXPECTED_TYPE]",
                    severity=SEVERITY_WARNING,
                    symbol="server.mcp",
                    message=(
                        f"server.mcp is {mcp_type!r}, expected FastMCP. "
                        "Verify tool registration is using FastMCP decorators."
                    ),
                ))

    # 5c: KSeFEnvironment enum exists in config
    config_mod, err = _try_import("mcp_ksef_pl.config")
    if config_mod is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_5",
            tag="[MISSING]",
            severity=SEVERITY_BLOCKING,
            symbol="mcp_ksef_pl.config",
            message=f"Could not import config module: {err}",
        ))
    else:
        env_cls = getattr(config_mod, "KSeFEnvironment", None)
        if env_cls is None:
            result.findings.append(CheckFinding(
                check_id="CHECK_5",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="KSeFEnvironment",
                message="KSeFEnvironment enum not found in mcp_ksef_pl.config.",
            ))
        else:
            required_envs = {"PRODUCTION", "TEST", "DEMO"}
            actual_envs = {e.name for e in env_cls}
            for env in sorted(required_envs):
                tag = "[OK]" if env in actual_envs else "[MISSING_ENV]"
                sev = SEVERITY_OK if env in actual_envs else SEVERITY_BLOCKING
                result.findings.append(CheckFinding(
                    check_id="CHECK_5",
                    tag=tag,
                    severity=sev,
                    symbol=f"KSeFEnvironment.{env}",
                    message=(
                        "Environment variant defined."
                        if env in actual_envs
                        else f"Required KSeF environment '{env}' missing from KSeFEnvironment enum."
                    ),
                ))

    # 5d: XSD schema directory presence (WARNING only — official schema must be downloaded)
    schemas_dir = Path(__file__).parent.parent / "src" / "mcp_ksef_pl" / "schemas"
    if schemas_dir.exists():
        xsd_files = list(schemas_dir.glob("*.xsd"))
        if xsd_files:
            result.findings.append(CheckFinding(
                check_id="CHECK_5",
                tag="[OK]",
                severity=SEVERITY_OK,
                symbol="src/mcp_ksef_pl/schemas/",
                message=f"XSD schema directory found with {len(xsd_files)} file(s): "
                        f"{', '.join(f.name for f in xsd_files)}",
            ))
        else:
            result.findings.append(CheckFinding(
                check_id="CHECK_5",
                tag="[MISSING_SCHEMA]",
                severity=SEVERITY_WARNING,
                symbol="src/mcp_ksef_pl/schemas/",
                message=(
                    "schemas/ directory exists but contains no .xsd files. "
                    "FA(2) XSD validation will be skipped at runtime. "
                    "[NEED: download FA_VAT_v1-0E.xsd from the Polish Ministry of Finance "
                    "and place it in src/mcp_ksef_pl/schemas/]"
                ),
            ))
    else:
        result.findings.append(CheckFinding(
            check_id="CHECK_5",
            tag="[MISSING_SCHEMA]",
            severity=SEVERITY_WARNING,
            symbol="src/mcp_ksef_pl/schemas/",
            message=(
                "schemas/ directory not found. "
                "FA(2) XSD validation will be skipped at runtime. "
                "[NEED: download FA_VAT_v1-0E.xsd from the Polish Ministry of Finance "
                "and place it in src/mcp_ksef_pl/schemas/]"
            ),
        ))

    return result


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_summary_table(report: AuditReport) -> str:
    lines: list[str] = []
    sep = "─" * 80

    lines.append(sep)
    lines.append("  mcp-ksef-pl  Pre-publish Audit Report")
    lines.append(f"  Generated  : {report.generated_at}")
    lines.append(f"  Pkg version: {report.pkg_version}")
    lines.append(f"  Core ver   : {report.core_version or 'not installed'}")
    lines.append(sep)

    for check in report.checks:
        status = "SKIPPED" if check.skipped else ("PASS" if check.passed else "FAIL")
        lines.append(f"\n  [{status}] {check.check_id}: {check.name}")
        if check.skipped:
            lines.append(f"         ↳ {check.skip_reason}")
            continue
        lines.append(
            f"         Blocking: {check.blocking_count}  "
            f"Warnings: {check.warning_count}  "
            f"OK: {sum(1 for f in check.findings if f.severity == SEVERITY_OK)}"
        )
        for finding in check.findings:
            if finding.severity in (SEVERITY_BLOCKING, SEVERITY_WARNING):
                indent = "    "
                tag_str = f"{finding.tag:<24}"
                msg = textwrap.fill(
                    finding.message,
                    width=72,
                    initial_indent=indent + tag_str + " ",
                    subsequent_indent=indent + " " * 25,
                )
                lines.append(msg)

    lines.append(f"\n{sep}")
    lines.append(
        f"  TOTAL — Blocking: {report.total_blocking}  "
        f"Warnings: {report.total_warnings}  "
        f"Exit code: {report.exit_code}"
    )
    verdict = {0: "PASS", 1: "WARNINGS", 2: "FAIL"}[report.exit_code]
    lines.append(f"  Verdict: {verdict}")
    lines.append(sep)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_audit() -> AuditReport:
    """Execute all checks and return the aggregated AuditReport. No side effects."""
    pkg_version = _get_installed_version("mcp-ksef-pl") or "0.0.0-dev"
    core_version = _get_installed_version("mcp-einvoicing-core")

    core_compat = True
    if core_version:
        spec = _read_core_version_spec_from_pyproject()
        if spec:
            core_compat = _version_in_range(core_version, spec)

    report = AuditReport(
        generated_at=datetime.now(UTC).isoformat(),
        pkg_version=pkg_version,
        core_version=core_version,
        core_version_compatible=core_compat,
    )

    report.checks.append(run_check_1())
    report.checks.append(run_check_2())
    report.checks.append(run_check_3())
    report.checks.append(run_check_4())
    report.checks.append(run_check_5())

    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pre-publish audit: mcp-ksef-pl vs mcp-einvoicing-core",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Exit codes:
          0  All checks passed
          1  Warnings only
          2  Blocking failures (publish should be blocked)
        """),
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write JSON report to this path (default: audit/report.json)",
        default=None,
    )
    parser.add_argument(
        "--fail-on",
        metavar="LEVEL",
        choices=["blocking", "warnings", "never"],
        default="blocking",
        help=(
            "When to exit non-zero: "
            "'blocking' (default) = only on BLOCKING findings; "
            "'warnings' = on any warning or blocking; "
            "'never' = always exit 0."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable table; only write JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_audit()

    output_path = Path(args.output) if args.output else Path(__file__).parent / "report.json"
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
