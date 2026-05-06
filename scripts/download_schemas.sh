#!/usr/bin/env bash
# Download KSeF XSD schemas from the CIRFMF GitHub repository.
#
# Two schemas are needed:
#
#   FA(2)  — used by generate_fa2_invoice / validate_fa2_invoice (KSeF v1, legacy)
#   FA(3)  — used by generate_fa3_invoice (KSeF API v2, required for new submissions)
#
# Reference copies of both schemas (for structural documentation) live in specs/.
# Place the downloaded files in src/mcp_ksef_pl/schemas/ to enable full XSD
# validation inside validate_fa2_invoice / (future) validate_fa3_invoice.
#
# Source: https://github.com/CIRFMF/ksef-docs/tree/main/faktury/schemy/FA
#
# Usage:
#   bash scripts/download_schemas.sh              # download both schemas
#   bash scripts/download_schemas.sh /path/fa3.xsd  # copy FA(3) from local file

set -euo pipefail

SCHEMA_DIR="$(dirname "$0")/../src/mcp_ksef_pl/schemas"
CIRFMF_BASE="https://raw.githubusercontent.com/CIRFMF/ksef-docs/main/faktury/schemy/FA"

FA2_FILE="$SCHEMA_DIR/schemat_FA2_v1-0E.xsd"
FA3_FILE="$SCHEMA_DIR/schemat_FA3_v1-0E.xsd"

mkdir -p "$SCHEMA_DIR"

_verify_xsd() {
  local f="$1"
  if grep -q "xs:schema\|xsd:schema" "$f" 2>/dev/null; then
    echo "  OK: $f"
  else
    echo "  WARNING: $f does not look like a valid XSD — check the content."
  fi
}

_download_or_skip() {
  local url="$1"
  local dest="$2"
  local label="$3"

  if [ -f "$dest" ]; then
    echo "$label already present: $dest"
    return 0
  fi

  echo "Downloading $label ..."
  if curl -fsSL "$url" -o "$dest"; then
    _verify_xsd "$dest"
  else
    echo ""
    echo "$label could not be downloaded automatically."
    echo "Manual steps:"
    echo "  1. Open: https://github.com/CIRFMF/ksef-docs/tree/main/faktury/schemy/FA"
    echo "  2. Download the raw file for $label."
    echo "  3. Place it at: $dest"
    echo ""
  fi
}

# If a path argument is given, treat it as the FA(3) schema source.
if [ "${1:-}" != "" ] && [ -f "$1" ]; then
  cp "$1" "$FA3_FILE"
  echo "Copied $1 → $FA3_FILE"
  _verify_xsd "$FA3_FILE"
  exit 0
fi

_download_or_skip \
  "$CIRFMF_BASE/schemat_FA(2)_v1-0E.xsd" \
  "$FA2_FILE" \
  "FA(2) schema"

_download_or_skip \
  "$CIRFMF_BASE/schemat_FA(3)_v1-0E.xsd" \
  "$FA3_FILE" \
  "FA(3) schema"

echo ""
echo "Done. Files in $SCHEMA_DIR:"
ls -lh "$SCHEMA_DIR" 2>/dev/null || echo "  (directory empty)"
