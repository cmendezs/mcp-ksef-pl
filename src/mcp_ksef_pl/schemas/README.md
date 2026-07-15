# KSeF XSD schemas (bundled, ships in the wheel)

Runtime XSD schemas used by `FA2Validator`/`FA3Validator` for XSD validation.
This directory is part of the `mcp_ksef_pl` package tree (`packages = ["src/mcp_ksef_pl"]`
in `pyproject.toml`), so every file here ships inside the built wheel and is loaded at
runtime via `importlib.resources.files("mcp_ksef_pl.schemas")` — no post-install
download step or repo-relative path lookup is required.

| File | Namespace | Description |
|---|---|---|
| `schemat_FA(2)_v1-0E.xsd` | `http://crd.gov.pl/wzor/2023/06/29/12648/` | FA(2) invoice schema (legacy, KSeF v1) |
| `schemat_FA(3)_v1-0E.xsd` | `http://crd.gov.pl/wzor/2025/06/25/13775/` | FA(3) invoice schema (mandatory for KSeF API v2) |

Source: official CIRFMF ksef-docs repository (`https://github.com/CIRFMF/ksef-docs`).
See `mcp-ksef-pl/specs/README.md` for provenance and retrieval dates.

Any XSD added to this directory ships in the wheel automatically. Do not place
files here that should not be redistributed.
