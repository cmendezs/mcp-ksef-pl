# mcp-ksef-pl — Specification assets

Reference files for KSeF FA(2) / FA(3) and KSeF API v2.
All files sourced from the official CIRFMF ksef-docs repository
(`https://github.com/CIRFMF/ksef-docs`).

| File | Description | Version | Retrieved |
|---|---|---|---|
| `schemat_FA(2)_v1-0E.xsd` | FA(2) invoice schema — namespace `http://crd.gov.pl/wzor/2023/06/29/12648/` | 1-0E | 2026-05-18 |
| `schemat_FA(3)_v1-0E.xsd` | FA(3) invoice schema (mandatory for KSeF API v2) — namespace `http://crd.gov.pl/wzor/2025/06/25/13775/` | 1-0E | 2026-05-18 |
| `ksef-api-v2-openapi.json` | KSeF REST API v2 OpenAPI specification | v2 | 2026-05-18 |
| `ksef-v2-fa3-migration-announcement-20250630.pdf` | Official MF announcement for FA(3) mandate and KSeF v2 rollout | — | 2026-05-18 |

## Key namespaces

| Format | XML namespace |
|---|---|
| FA(2) | `http://crd.gov.pl/wzor/2023/06/29/12648/` |
| FA(3) | `http://crd.gov.pl/wzor/2025/06/25/13775/` |

## Validation

- **FA(2)**: `FA2Validator` in `src/mcp_ksef_pl/validator.py` uses `schemat_FA(2)_v1-0E.xsd`
  via `specs/`. The XSD is loaded at runtime via `importlib.resources`.
- **FA(3)**: `FA3Validator` in `src/mcp_ksef_pl/validator.py` uses `schemat_FA(3)_v1-0E.xsd`
  via `specs/`.

## Update process

When MF publishes a new schema version:
1. Download the new XSD from `https://github.com/CIRFMF/ksef-docs`.
2. Replace the file here and update the version and retrieved date in this table.
3. Update the `_SCHEMA_VERSION` constant in the corresponding validator class.
4. Run the test suite to verify no regressions.
