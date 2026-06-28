# Release Process for mcp-ksef-pl

This document describes how to release a new version of `mcp-ksef-pl` to PyPI and the official MCP registry.

## One-Time Setup Requirements

**PyPI Trusted Publishing:**
PyPI publishing is fully automated via OIDC (no token stored). The Trusted Publisher is configured on PyPI under `cmendezs/mcp-ksef-pl`, workflow `publish.yml`, environment `pypi`. No `.env` or secret needed.

**MCP Publisher CLI:**
Binary installed at `~/.local/bin/mcp-publisher` (already in `PATH`). To update:
```bash
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_darwin_arm64.tar.gz" \
  | tar xzf - -C ~/.local/bin/
```

**MCP Registry Authentication:**
Authenticate once with GitHub (device flow):
```bash
mcp-publisher login github
```

## Release Steps

**Step 1 — Version bump:** update `version` in `pyproject.toml` and `server.json` (top-level and `packages[].version`).

**Step 2 — Commit, tag and push:**
```bash
git add pyproject.toml server.json
git commit -m "release: v{VERSION} — {summary}"
git push origin main
git tag v{VERSION}
git push origin v{VERSION}
```
GitHub Actions publishes to PyPI automatically on tag push.

**Step 3 — MCP registry:**
```bash
mcp-publisher publish
```

## Changelog

### [0.4.0] - 2026-06-28
#### Added
- `KSeFInvoice.from_lines()` classmethod: auto-computes totals from line items and tax lines
- `KSeFParty._sync_nip_to_vat_id` model validator: syncs NIP to `vat_id` for core serializer compatibility
- Integration test scaffold with `tests/integration/` and manual-dispatch GitHub Actions workflow
- Expanded KSeF authentication section in README.md and README.pl.md

#### Changed
- **[PL-FA3-2]** All tool signatures (`generate_fa2_invoice`, `generate_fa3_invoice`, `generate_peppol_invoice`) now accept `KSeFInvoice` directly; `_doc_to_ksefinvoice` shim removed
- Peppol generator rewritten to delegate to core `EN16931UBLSerializer` via minimal `_PLUBLSerializer` subclass (FR/DE pattern)

#### Resolved
- **[PL-INV-1]** FA(3) namespace verified: `http://crd.gov.pl/wzor/2025/06/25/13775/`
- **[PL-INV-2]** PINT-PL confirmed absent (404 on OpenPeppol docs, 2026-06-27)
- **[PL-FA3-1]** FA(3) generator complete end-to-end

### [0.2.2] - 2026-05-31
#### Added
- **[PL-CORE-1]** `KSeFPeppolUBLSerializer(EN16931UBLSerializer)`: injects Peppol BIS 3.0
  `ProfileID` after `CustomizationID`; resolves `KSeFParty.nip` to `PL{nip}` `CompanyID`.
- **[PL-CORE-1]** `KSeFPeppolUBLParser(EN16931UBLParser)`: returns `KSeFInvoice` with
  `KSeFParty` objects; extracts NIP from `PL`-prefixed VAT IDs.
- 14 tests covering serialiser output and full round-trip parser behaviour.
- Both classes scoped to the Peppol BIS 3.0 cross-border profile; KSeF FA(2)/FA(3)
  generators are unchanged.
#### Fixed
- CI: retagged `v0.2.2` to include `publish.yml` YAML fix (bare `python -c "` →
  `run: |` heredoc).

### [0.2.0] - 2026-05-21
#### Added / Fixed (Sprint 1–4, all 17 PL findings resolved)
- **[PL-1.1] HIGH:** `DataWytworzenieFa` typo fixed in `generator.py` and `validator.py`.
- **[PL-2.1] HIGH:** OO/NP exemption code routing fixed: ZW to P_13_5, OO to P_13_6_1,
  NP to P_13_7.
- **[PL-1.2] MEDIUM:** FA(3) namespace guard added in `submit_invoice_to_ksef`.
- **[PL-3.1] MEDIUM:** `validTo` expiry check added in `_pick_encryption_cert`.
- **[PL-3.2] MEDIUM:** `_raise_ksef_error` helper parses `exceptionCode` and `message`
  from KSeF JSON error bodies.
- **[PL-6.2] MEDIUM:** `FA3Validator` added; `validate_fa3_invoice` tool exposed;
  FA(2) XSD path fixed.
- **[PL-4.1]** Correction invoice support: `KSeFCorrectionRef` model,
  `<FakturaKorygowana>` block, 50,000-line guard.
- **[PL-2.2]** `IPKSeF` and `LinkDoPlatnosci` fields added to FA(3) payment block.
- **[PL-2.3]** `<Zalacznik>` attachment support via `KSeFAttachment` model.
- **[PL-2.4]** `Podmiot3` (up to 100 entries) and `PodmiotUpowazniony` implemented.
- **[PL-2.5]** `gln: str | None` added to `KSeFParty`; `<GLN>` emitted when present.
- **[PL-3.4]** `session_token_expires_at` metadata key added; pre-flight check raises
  on expired tokens.
- `KSeFFA3Options` model added; `KSeFParty` extended with `nip`, `eu_vat_country`,
  `eu_vat_id`, `gln`; 64 tests passing; ruff clean.
- Core floor bumped to `>=1.2.0` (`generator.py` reads `PartyAddress.gln`).

### [0.1.0]
#### Added
- Initial release: KSeF FA(2) XML generation and validation; Polish NIP and REGON
  checksum validation.
- Peppol BIS 3.0 / EN 16931 UBL 2.1 generator; pre-publish audit gate.
- KSeF API v2 migration: AES-256-CBC + RSA-OAEP encryption, session-based submission,
  updated endpoints.
- FA(3) XML generator: namespace `http://crd.gov.pl/wzor/2025/06/25/13775/`,
  `WariantFormularza=3`, mandatory sub-elements.

---

## Notes

- The MCP registry does **not** sync automatically with PyPI or GitHub — step 3 is required for every release.
- The `server.json` description field must be **≤ 100 characters**.
- PyPI rejects re-uploads of the same version — always bump before tagging.
