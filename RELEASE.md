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

### [0.8.4] - 2026-08-31
#### Fixed
- **[PL-ERR-1]** `KSeFClient._request`'s KSeF-structured-error re-raise (`_raise_ksef_error`) was unreachable dead code — it only ran when `exc.response_body` was truthy, but `mcp-einvoicing-core`'s `PlatformError` never set that attribute, so every KSeF error surfaced as core's generic `HTTP error <code>` message instead of KSeF's own `{"exceptionCode", "message"}` body. Fixed by `mcp-einvoicing-core` v1.28.0 (`PlatformError.response_body`); the `hasattr` guard is removed since the attribute is now always present.
- **[PL-TZ-1]** `_to_iso_datetime` passed a naive (offset-less) full datetime string straight through to `search_documents`'s `dateRange` filter. Now assumed UTC and gets `+00:00` appended; a value already carrying a `Z` suffix or an explicit offset is unaffected.

#### Added
- `KSeFClient._request` now logs the KSeF API v2.6.0 `X-System-Warning` response header at `WARNING` level when present on an otherwise-successful response.

Raises the core lower-bound pin to `>=1.28.0` (was `>=1.27.0`). Found during the KSeF API v2.1.1→v2.7.1 delta review, regulatory-watch issue [#10](https://github.com/cmendezs/mcp-ksef-pl/issues/10).

### [0.8.3] - 2026-08-31
#### Fixed
- **[PL-DISC-1]** KSeF API v2.4.0 (PRD-live since 2026-07-16) rejects an otherwise schema-valid FA(2)/FA(3) document containing a W3C XML 1.0 Appendix C "discouraged" code point (C1 controls + DEL, certain noncharacters); `xml_escape()` alone does not filter these. `generator.py` now routes every text field through a new `_escape()` wrapper that applies `mcp-einvoicing-core`'s new `sanitize_xml_text()` (v1.27.0) before escaping, rejecting generation with `DocumentGenerationError` rather than silently mutating a legally-binding invoice field. Added `tests/test_generator.py::TestDiscouragedCharacterSanitization`.

Raises the core lower-bound pin to `>=1.27.0` (was `>=1.20.0`). Found during the KSeF API v2.1.1→v2.7.1 delta review, regulatory-watch issue [#10](https://github.com/cmendezs/mcp-ksef-pl/issues/10).

### [0.8.2] - 2026-08-24
#### Fixed
- `FA2Parser` line-item xpath looked for a `<FaWiersze>` wrapper around `<FaWiersz>` rows that does not exist in the FA(2) schema (`<FaWiersz>` is a direct child of `<Fa>`), so `parse()` always returned an empty `lines` list for any real FA(2) XML, including this package's own generator output. Fixed to read `<FaWiersz>` directly.
- `due_date` was reading `<P_6>` (date of supply/delivery/service completion), not the payment due date, which lives in `<Platnosc>/<TerminPlatnosci>/<Termin>` (same schema fact already applied to `FA2Generator` in the v0.8.1 `PL-PAY-1` fix). `<P_6>` is now parsed separately under `supply_date`.
- Added `tests/test_parser.py` — no test file previously existed for `FA2Parser`, which is how both bugs went unnoticed despite `parse_fa2_invoice` being a live registered MCP tool.

### [0.8.1] - 2026-08-24
#### Fixed
- **[PL-PAY-1]** FA(2) `<Platnosc>` block structural conformance, deferred as a known gap since v0.5.0. `_payment_block` emitted a non-existent invoice-level `<P_6>` for `due_date` and an unwrapped `<RachunekBankowy>` spliced in before `<RodzajFaktury>`; `due_date`/IBAN now emit inside a `<Platnosc>` block (`TerminPlatnosci`, `FormaPlatnosci`, `RachunekBankowy`) positioned after `<FaWiersz>`, mirroring FA(3)'s already-correct shape (`_fa3_platnosc_block`). Added `tests/test_fa2_xsd_conformance.py` (payment-bearing FA(2) fixture, generate→XSD-validate) plus a structural unit test, since `sample_invoice` alone (no `due_date`/`payment_means`) did not exercise this path.

### [0.8.0] - 2026-08-24
#### Changed
- **[core v1.20.0]** `peppol_send` now emits a real `wsse:Security` message signature. Core's AS4 transport client's `_apply_message_signature` previously computed a signature and discarded it, sending unsigned outbound messages. Wire-level behavior change, not independently validated against a live sandbox Peppol AP at time of publish — the signing code is shared core logic, not PL-specific, so no per-package sandbox gate was required.
- Lower-bound pin on `mcp-einvoicing-core` raised to `>=1.20.0` (was `>=1.19.0`).

#### Added
- New `xslt2` extra: `mcp-einvoicing-core[xslt2]>=1.20.0`. This package had no `[xslt2]` extra before — it is required by the new EUSR/TSR reporting and MLS tools below. `saxonche` also added to the `dev` extra so reporting/MLS tests run.
- Mounted three new opt-in core plugins in `server.py`, alongside the existing Peppol tool plugin: `register_peppol_reporting_tools` (`validate_eusr_report`, `validate_tsr_report`; requires `[xslt2]`), `register_peppol_mls_tools` (`validate_mls_message`, `build_mls_message`; requires `[xslt2]`), and `register_en16931_codelist_tools` (13 `list_*`/`check_*` pairs; requires `EINVOICING_EN16931_CODELIST_DIR`). `peppol_directory_search` arrives automatically via the existing `register_peppol_tools` mount.
- Server-registration smoke test asserting the new tools register.

### [0.7.0] - 2026-08-21
#### Changed
- **[ARCH-CONVERGE-PL]** `server.py` converted from a raw `FastMCP` instance to `EInvoicingMCPServer`/`register_plugin`, matching the other country packages. Mounts the shared core Peppol tool plugin (`mcp_einvoicing_core.peppol.tools.register_peppol_tools`) with a Poland-specific identifier adapter that normalizes a bare NIP to the `9945:<digits>` Peppol scheme (`PL:VAT`, per the OpenPeppol eDEC Participant Identifier Schemes code list v9.7). PL gains 12 new Peppol network tools it did not have before: `peppol_lookup_participant`, `peppol_get_service_endpoint`, `resolve_peppol_dns`, `peppol_send`, and 8 eDEC codelist tools.
- Lower-bound pin on `mcp-einvoicing-core` raised to `>=1.19.0` (was `>=1.18.0`), required for `register_peppol_tools`.
- Removed the direct `fastmcp` dependency; no longer imported directly now that `server.py` uses `EInvoicingMCPServer` (still available transitively via `mcp-einvoicing-core`).

### [0.6.0] - 2026-08-20
#### Added
- **[CORE-EN16931-BASE-SCHEMATRON-1]** `validate_peppol_invoice` tool, closing the gap where this package's Peppol path (`generate_peppol_invoice`/`peppol/parser.py`/`peppol/serializer.py`) had no validation tool at all. Delegates to `mcp-einvoicing-core`'s bundled CEN EN16931 base Schematron (`en16931_base_schematron_validator`, core >= 1.18.0). Checks the ~50 CEN `BR-*` structural/arithmetic rules only — does NOT check the Peppol-specific overlay (profile/process ID registration, `EndpointID` scheme, narrowed code lists). Every result carries `metadata.scope="en16931-base-only"` and an explicit warning; never presented as full Peppol BIS3 conformance. See `context-library/decisions/peppol-schematron-artifact.md` for why the overlay itself still cannot ship (no confirmed OpenPeppol redistribution rights).

#### Changed
- Lower-bound pin on `mcp-einvoicing-core` raised to `>=1.18.0` (was `>=1.15.0`) for the new `schematron_artifacts` module.

### [0.5.1] - 2026-08-14
#### Changed
- **[PL-API-2026-08]** reconciled to KSeF production API v2.1.1 (2026-02-13): diffed the full v2.0.1→v2.1.1 CIRFMF changelog against all 8 implemented endpoints; delta clusters entirely on `/auth/*` and `/permissions/*`/`/tokens`/`/testdata/*` areas this package does not implement beyond the challenge/redeem flow
- `lifecycle.py` docstrings corrected from stale v1-style auth paths (`/api/online/Session/AuthorisationChallenge`, `AuthoriseXades`) to the actual v2 flow (`/auth/challenge` → `/auth/xades-signature` → `/auth/token/redeem`)

### [0.5.0] - 2026-07-15
#### Added
- MF public-key SPKI SHA-256 pinning (`security/mf_pinning.py`), wired into `submit_document()`; inert by default (empty allowlist)

#### Fixed
- **[PL-6.3]** FA(2)/FA(3) XSDs (plus transitive `StrukturyDanych`/`ElementarneTypyDanych`/`KodyKrajow` chain) now bundled under `src/mcp_ksef_pl/schemas/`, loaded via `importlib.resources`; XSD validation runs for every installed user
- **[PL-PEP-1]** removed ad-hoc Peppol `<cbc:ProfileID>` overrides; consumes core `business_process` directly
- **[PL-3.5]** `subjectType` default normalized to PascalCase
- **[PL-2.7]** `Platnosc` element order/nesting corrected
- **[PL-2.8]** unknown VAT rate now raises `DocumentGenerationError` instead of silently defaulting to 23%
- **[PL-5.2]** NIP/REGON validation delegates to core `TaxIdentifier`
- FA(2) generator brought into full schema conformance (collateral fix, surfaced by PL-6.3)
- Pre-existing `XSDValidationError` constructor bug and validate-vs-raise mismatch in `_xsd_validate()`

#### Changed (breaking)
- **[PL-4.2]** correction block rewritten as `DaneFaKorygowanej`; `KSeFCorrectionRef` field shape changed
- **[PL-2.6]** `Zalacznik`/`BlokDanych` re-placed at correct XSD position; `KSeFAttachment` field shape changed

#### Known gaps
- **[PL-PAY-1]** `FA2Generator._payment_block` still emits an invalid `<P_6>`/unwrapped `RachunekBankowy`; deferred to a follow-up release

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
