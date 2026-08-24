# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.8.1] - 2026-08-24

### Fixed
- **PL-PAY-1:** FA(2) `<Platnosc>` (payment) block was structurally invalid. `_payment_block` emitted a non-existent invoice-level `<P_6>` element for `due_date` and an unwrapped `<RachunekBankowy>` spliced in before `<RodzajFaktury>`. `<P_6>` exists in the FA(2) schema but means "date of supply/service completion", not "payment due date" — it was also positioned wrong even on that reading. `due_date` and IBAN now emit inside a `<Platnosc>` block (`TerminPlatnosci`, `FormaPlatnosci`, `RachunekBankowy`), positioned as a sibling of `<FaWiersz>` after the invoice lines, mirroring `_fa3_platnosc_block`'s already-correct FA(3) shape. Not caught by v0.5.0's XSD-conformance tests because `sample_invoice` had no `due_date`/`payment_means`; added `tests/test_fa2_xsd_conformance.py` (payment-bearing FA(2) fixture, generate→XSD-validate) plus a structural unit test in `tests/test_generator.py`.

---

## [0.8.0] - 2026-08-24

### Changed
- **`peppol_send` now emits a real `wsse:Security` message signature.** `mcp-einvoicing-core` v1.20.0 fixed the AS4 transport client's `_apply_message_signature`, which previously computed a signature and discarded it, sending unsigned outbound messages. This is an API-compatible, wire-level behavior change — no code in this package changed to pick it up, but every outbound message sent through this package's `peppol_send` is now actually signed. **Not yet validated against a live sandbox Peppol AP**; treat as unverified at the transport level until that validation runs.
- Lower-bound pin on `mcp-einvoicing-core` raised to `>=1.20.0` (was `>=1.19.0`).

### Added
- New `xslt2` extra: `mcp-einvoicing-core[xslt2]>=1.20.0`. This package had no `[xslt2]` extra before — it is required by the new EUSR/TSR reporting and MLS tools below. `saxonche` also added to the `dev` extra so reporting/MLS tests run.
- Mounted three new opt-in core plugins in `server.py`, alongside the existing Peppol tool plugin:
  - `register_peppol_reporting_tools` (`mcp_einvoicing_core.peppol.reporting_tools`) — `validate_eusr_report`, `validate_tsr_report` (End User / Transaction Statistics Reports). Requires the `[xslt2]` extra.
  - `register_peppol_mls_tools` (`mcp_einvoicing_core.peppol.mls_tools`) — `validate_mls_message`, `build_mls_message` (Message Level Status). Requires the `[xslt2]` extra.
  - `register_en16931_codelist_tools` (`mcp_einvoicing_core.en16931_codelist_tools`) — 13 `list_*`/`check_*` pairs plus `get_en16931_codelist_version` for the EN 16931 semantic code lists. Requires `EINVOICING_EN16931_CODELIST_DIR` to be set to a local copy of the CEF Digital code lists (not bundled).
  - `peppol_directory_search` (public Peppol Directory search) arrives automatically via the existing `register_peppol_tools` mount — no `server.py` change needed for this one.
- All new tools are mounted unconditionally; they raise a clear error at call time (not at registration) when their extra or data directory is missing, matching the existing eDEC codelist tool pattern.

---

## [0.7.0] - 2026-08-22

### Added
- Initial changelog. Prior release history is recorded in the Git tags and
  GitHub Releases for this repository.
