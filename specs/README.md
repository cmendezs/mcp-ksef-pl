# mcp-ksef-pl — Specification assets

Reference files for KSeF FA(2) / FA(3) and KSeF API v2.
All files sourced from the official CIRFMF ksef-docs repository
(`https://github.com/CIRFMF/ksef-docs`).

## Runtime artifacts (shipped in the wheel)

The FA(2) and FA(3) XSDs live under `src/mcp_ksef_pl/schemas/`, not here — they
are part of the packaged tree so they ship inside the wheel and are loaded via
`importlib.resources.files("mcp_ksef_pl.schemas")` at runtime. See
[`src/mcp_ksef_pl/schemas/README.md`](../src/mcp_ksef_pl/schemas/README.md).

| File | Description | Version | Retrieved |
|---|---|---|---|
| `src/mcp_ksef_pl/schemas/schemat_FA(2)_v1-0E.xsd` | FA(2) invoice schema — namespace `http://crd.gov.pl/wzor/2023/06/29/12648/` | 1-0E | 2026-05-18 |
| `src/mcp_ksef_pl/schemas/schemat_FA(3)_v1-0E.xsd` | FA(3) invoice schema (mandatory for KSeF API v2) — namespace `http://crd.gov.pl/wzor/2025/06/25/13775/` | 1-0E | 2026-05-18 |

## Reference artifacts (not shipped)

Kept here for provenance and manual reference only. Not loaded at runtime and
not part of the wheel.

| File | Description | Version | Retrieved |
|---|---|---|---|
| `ksef-api-v2-openapi.json` | KSeF REST API v2 OpenAPI specification | v2 | 2026-05-18 |
| `ksef-v2-fa3-migration-announcement-20250630.pdf` | Official MF announcement for FA(3) mandate and KSeF v2 rollout | — | 2026-05-18 |

## Key namespaces

| Format | XML namespace |
|---|---|
| FA(2) | `http://crd.gov.pl/wzor/2023/06/29/12648/` |
| FA(3) | `http://crd.gov.pl/wzor/2025/06/25/13775/` |

## Validation

- **FA(2)**: `FA2Validator` in `src/mcp_ksef_pl/validator.py` loads
  `schemat_FA(2)_v1-0E.xsd` from `src/mcp_ksef_pl/schemas/` via `importlib.resources`.
- **FA(3)**: `FA3Validator` in `src/mcp_ksef_pl/validator.py` loads
  `schemat_FA(3)_v1-0E.xsd` from `src/mcp_ksef_pl/schemas/` via `importlib.resources`.

## Update process

When MF publishes a new schema version:
1. Download the new XSD from `https://github.com/CIRFMF/ksef-docs`.
2. Replace the file under `src/mcp_ksef_pl/schemas/` and update the version and
   retrieved date in the table above.
3. Update the `_SCHEMA_VERSION` constant in the corresponding validator class.
4. Run the test suite to verify no regressions.
