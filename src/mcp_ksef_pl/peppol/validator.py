"""Peppol BIS 3.0 / EN 16931 UBL invoice validation.

Delegates to mcp-einvoicing-core's bundled CEN EN16931 base Schematron
(``en16931_base_schematron_validator``, core >= 1.18.0 —
[CORE-EN16931-BASE-SCHEMATRON-1]). This closes the gap where this package's
Peppol path (generator/parser/serializer) had no validation tool at all.

Scope: EN 16931 base rules only (structural + arithmetic/totals, ~50 BR-*
rules). Does NOT check the Peppol-specific overlay (profile/process ID
registration, EndpointID scheme, narrowed code lists) — the Peppol overlay
Schematron has no confirmed redistribution rights and is not bundled
anywhere. Every result carries metadata.scope="en16931-base-only" and an
explicit warning; never present this as full Peppol BIS3 conformance. See
context-library/decisions/peppol-schematron-artifact.md (root repo) for the
full licensing investigation.
"""

from __future__ import annotations

import logging

from mcp_einvoicing_core import BaseDocumentValidator, DocumentValidationResult

_log = logging.getLogger(__name__)

_SCHEMA_VERSION = "Peppol BIS 3.0 / EN16931 (base rules only)"

# Carried on every result: this validator checks the CEN EN16931 base rules
# only, not the Peppol-specific overlay. A document can pass this and still
# be rejected by a real Peppol Access Point.
_EN16931_BASE_ONLY_SCOPE_WARNING = (
    "EN16931-BASE-ONLY-SCOPE: this validates the CEN EN16931 base rules "
    "(structural + arithmetic/totals) only. Peppol-specific overlay rules "
    "(profile/process ID registration, EndpointID scheme, narrowed code "
    "lists) are NOT checked — this is not a full Peppol BIS3 conformance "
    "result. See context-library/decisions/peppol-schematron-artifact.md."
)

# Emitted when core's bundled EN16931-base Schematron could not be loaded
# (e.g. the [xslt2] extra is not installed).
_VALIDATION_UNAVAILABLE = (
    "PEPPOL-VALIDATION-UNAVAILABLE: core's bundled EN16931-base Schematron "
    "validator could not be loaded. Install mcp-einvoicing-core[xslt2] to "
    "enable validation."
)


class PeppolValidator(BaseDocumentValidator):
    """Validates Peppol BIS 3.0 / EN 16931 UBL invoices against the CEN base ruleset.

    See module docstring for scope (base rules only, no Peppol overlay).
    """

    def __init__(self) -> None:
        self._schematron = None
        try:
            from mcp_einvoicing_core.schematron_artifacts import (  # noqa: PLC0415
                en16931_base_schematron_validator,
            )

            self._schematron = en16931_base_schematron_validator()
            _log.info("Loaded core's bundled EN16931-base Schematron.")
        except ImportError as exc:
            _log.warning(
                "Core's bundled EN16931-base Schematron requires XSLT 2.0/3.0 "
                "(Saxon-HE); install mcp-einvoicing-core[xslt2] to enable it. %s",
                exc,
            )
        except Exception as exc:
            _log.warning("Failed to load core's bundled EN16931-base Schematron: %s", exc)

    def get_schema_version(self) -> str:
        return _SCHEMA_VERSION

    async def validate(self, document_content: str | bytes) -> DocumentValidationResult:
        if not self._schematron:
            return DocumentValidationResult(
                valid=False,
                errors=[_VALIDATION_UNAVAILABLE],
                warnings=[],
                metadata={"engine": "unavailable"},
            )

        xml_bytes = (
            document_content.encode("utf-8")
            if isinstance(document_content, str)
            else document_content
        )
        result = self._schematron.validate(xml_bytes, profile="peppol-bis-3", syntax="UBL")
        return DocumentValidationResult(
            valid=result.is_valid,
            errors=[f"{m.rule_id}: {m.text}" for m in result.errors],
            warnings=[
                _EN16931_BASE_ONLY_SCOPE_WARNING,
                *[f"{m.rule_id}: {m.text}" for m in result.warnings],
            ],
            metadata={"engine": "schematron-xslt", "scope": "en16931-base-only"},
        )
