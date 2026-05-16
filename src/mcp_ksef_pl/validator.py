"""FA(2) XML validator — XSD schema + KSeF business rules.

The official XSD is published by the Polish Ministry of Finance at:
  https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/
Download FA_VAT_v1-0E.xsd and place it at src/mcp_ksef_pl/schemas/FA_VAT_v1-0E.xsd
to enable full XSD validation.  Without the file, only structural/business checks run.
"""

import re
from pathlib import Path

from mcp_einvoicing_core import (
    BaseDocumentValidator,
    DocumentValidationResult,
    XSDValidationError,
)
from mcp_einvoicing_core.xml_utils import safe_fromstring, safe_parser

_FA2_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"
_SCHEMA_VERSION = "FA(2) v1-0E"
_SCHEMA_FILENAME = "FA_VAT_v1-0E.xsd"


def _load_lxml() -> tuple[bool, object]:
    try:
        from lxml import etree  # type: ignore[import]

        return True, etree
    except ImportError:
        return False, None


class FA2Validator(BaseDocumentValidator):
    """Validates KSeF FA(2) XML against XSD and business rules."""

    def get_schema_version(self) -> str:
        return _SCHEMA_VERSION

    def get_schema_path(self) -> str | None:
        schema_dir = Path(__file__).parent / "schemas"
        path = schema_dir / _SCHEMA_FILENAME
        return str(path) if path.exists() else None

    async def validate(self, xml_content: str) -> DocumentValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, object] = {"schema_version": _SCHEMA_VERSION}

        # --- XSD validation (optional — requires lxml + schema file) ---
        has_lxml, etree = _load_lxml()
        schema_path = self.get_schema_path()

        if has_lxml and schema_path and etree is not None:
            try:
                xsd_doc = etree.parse(schema_path, safe_parser())
                schema = etree.XMLSchema(xsd_doc)
                doc = safe_fromstring(xml_content.encode())
                if not schema.validate(doc):
                    xsd_errors = [str(e) for e in schema.error_log]
                    raise XSDValidationError(
                        message="FA(2) XSD validation failed",
                        schema_version=_SCHEMA_VERSION,
                        lxml_errors=xsd_errors,
                    )
                metadata["xsd_validated"] = True
            except XSDValidationError:
                raise
            except Exception as exc:
                warnings.append(f"XSD validation skipped due to parse error: {exc}")
                metadata["xsd_validated"] = False
        else:
            reason = (
                "lxml not installed." if not has_lxml
                else f"schema file not found at {_SCHEMA_FILENAME}."
            )
            warnings.append("XSD validation skipped: " + reason)
            metadata["xsd_validated"] = False

        # --- Business rules (always run) ---
        errors.extend(self._check_business_rules(xml_content))

        return DocumentValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )

    def _check_business_rules(self, xml_content: str) -> list[str]:
        errors: list[str] = []

        # Namespace presence
        if _FA2_NS not in xml_content:
            errors.append(f"Expected FA(2) namespace '{_FA2_NS}' not found.")

        # Mandatory header fields
        for tag in ("<KodFormularza", "<WariantFormularza>", "<DataWytworzenieFa>"):
            if tag not in xml_content:
                errors.append(f"Missing mandatory header element: {tag.strip('<')}.")

        # Seller NIP (Podmiot1 block)
        if "<Podmiot1>" not in xml_content:
            errors.append("Missing seller block <Podmiot1>.")

        # Buyer block
        if "<Podmiot2>" not in xml_content:
            errors.append("Missing buyer block <Podmiot2>.")

        # Invoice date P_1
        if "<P_1>" not in xml_content:
            errors.append("Missing invoice date <P_1>.")
        else:
            match = re.search(r"<P_1>(\d{4}-\d{2}-\d{2})</P_1>", xml_content)
            if not match:
                errors.append("<P_1> must contain a date in YYYY-MM-DD format.")

        # Invoice number P_2
        if "<P_2>" not in xml_content:
            errors.append("Missing invoice number <P_2>.")

        # Gross total P_15
        if "<P_15>" not in xml_content:
            errors.append("Missing gross total <P_15>.")

        # Invoice lines
        if "<FaWiersze>" not in xml_content:
            errors.append("Missing invoice lines block <FaWiersze>.")

        return errors
