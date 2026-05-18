"""FA(2) and FA(3) XML validators — XSD schema + KSeF business rules.

FA(2): XSD loaded from specs/schemat_FA(2)_v1-0E.xsd (relative to the package root).
FA(3): XSD loaded from specs/schemat_FA(3)_v1-0E.xsd.

Both validators require lxml for XSD validation.  Without lxml only the
structural / business-rule checks run.
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
_FA3_NS = "http://crd.gov.pl/wzor/2025/06/25/13775/"

_FA2_SCHEMA_VERSION = "FA(2) v1-0E"
_FA3_SCHEMA_VERSION = "FA(3) v1-0E"

# specs/ lives two levels above this file: src/mcp_ksef_pl/ → mcp-ksef-pl/specs/
_SPECS_DIR = Path(__file__).parent.parent.parent / "specs"


def _load_lxml() -> tuple[bool, object]:
    try:
        from lxml import etree  # type: ignore[import]

        return True, etree
    except ImportError:
        return False, None


def _xsd_validate(
    xml_content: str,
    schema_path: str | None,
    schema_version: str,
    errors: list[str],
    warnings: list[str],
    metadata: dict[str, object],
) -> None:
    """Run XSD validation if lxml and the schema file are available."""
    has_lxml, etree = _load_lxml()
    if has_lxml and schema_path and etree is not None:
        try:
            xsd_doc = etree.parse(schema_path, safe_parser())
            schema = etree.XMLSchema(xsd_doc)
            doc = safe_fromstring(xml_content.encode())
            if not schema.validate(doc):
                xsd_errors = [str(e) for e in schema.error_log]
                raise XSDValidationError(
                    message=f"{schema_version} XSD validation failed",
                    schema_version=schema_version,
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
            else f"schema file not found at {schema_path!r}."
        )
        warnings.append("XSD validation skipped: " + reason)
        metadata["xsd_validated"] = False


class FA2Validator(BaseDocumentValidator):
    """Validates KSeF FA(2) XML against XSD and business rules."""

    def get_schema_version(self) -> str:
        return _FA2_SCHEMA_VERSION

    def get_schema_path(self) -> str | None:
        path = _SPECS_DIR / "schemat_FA(2)_v1-0E.xsd"
        return str(path) if path.exists() else None

    async def validate(self, xml_content: str) -> DocumentValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, object] = {"schema_version": _FA2_SCHEMA_VERSION}

        _xsd_validate(
            xml_content, self.get_schema_path(), _FA2_SCHEMA_VERSION,
            errors, warnings, metadata,
        )
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
        for tag in ("<KodFormularza", "<WariantFormularza>", "<DataWytworzeniaFa>"):
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


class FA3Validator(BaseDocumentValidator):
    """Validates KSeF FA(3) XML against XSD and business rules (PL-6.2)."""

    def get_schema_version(self) -> str:
        return _FA3_SCHEMA_VERSION

    def get_schema_path(self) -> str | None:
        path = _SPECS_DIR / "schemat_FA(3)_v1-0E.xsd"
        return str(path) if path.exists() else None

    async def validate(self, xml_content: str) -> DocumentValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, object] = {"schema_version": _FA3_SCHEMA_VERSION}

        _xsd_validate(
            xml_content, self.get_schema_path(), _FA3_SCHEMA_VERSION,
            errors, warnings, metadata,
        )
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
        if _FA3_NS not in xml_content:
            errors.append(f"Expected FA(3) namespace '{_FA3_NS}' not found.")

        # Mandatory header fields
        for tag in ("<KodFormularza", "<WariantFormularza>", "<DataWytworzeniaFa>"):
            if tag not in xml_content:
                errors.append(f"Missing mandatory header element: {tag.strip('<')}.")

        # Seller block
        if "<Podmiot1>" not in xml_content:
            errors.append("Missing seller block <Podmiot1>.")

        # Buyer block (FA(3) mandates JST and GV flags)
        if "<Podmiot2>" not in xml_content:
            errors.append("Missing buyer block <Podmiot2>.")
        else:
            if "<JST>" not in xml_content:
                errors.append("Missing mandatory FA(3) buyer flag <JST>.")
            if "<GV>" not in xml_content:
                errors.append("Missing mandatory FA(3) buyer flag <GV>.")

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

        # RodzajFaktury (mandatory in FA(3))
        if "<RodzajFaktury>" not in xml_content:
            errors.append("Missing mandatory FA(3) element <RodzajFaktury>.")

        # Adnotacje with FA(3)-specific sub-elements
        if "<Adnotacje>" not in xml_content:
            errors.append("Missing mandatory FA(3) element <Adnotacje>.")
        else:
            for sub in ("<Zwolnienie>", "<NoweSrodkiTransportu>", "<PMarzy>"):
                if sub not in xml_content:
                    errors.append(f"Missing mandatory FA(3) Adnotacje sub-element {sub}.")

        # FA(3) must NOT use the FA(2) <FaWiersze> wrapper
        if "<FaWiersze>" in xml_content:
            errors.append(
                "FA(3) must not use <FaWiersze> wrapper; "
                "<FaWiersz> elements are direct children of <Fa>."
            )

        return errors
