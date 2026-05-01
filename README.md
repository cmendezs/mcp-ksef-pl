# mcp-ksef-pl

MCP server for Polish electronic invoicing — **KSeF (FA(2))** and **Peppol BIS Billing 3.0 / EN 16931**.

Built on top of [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core).

## Features

| Tool | Description |
|------|-------------|
| `generate_fa2_invoice` | Generate a KSeF FA(2) XML invoice from structured data |
| `validate_fa2_invoice` | Validate FA(2) XML against XSD + Polish business rules |
| `parse_fa2_invoice` | Parse FA(2) XML into a structured dictionary |
| `submit_invoice_to_ksef` | Submit an invoice to the KSeF platform |
| `get_ksef_invoice_status` | Poll the status of a submitted KSeF invoice |
| `search_ksef_invoices` | Query invoices by date range and direction |
| `validate_polish_nip` | Validate a Polish NIP (10-digit tax ID) |
| `validate_polish_regon` | Validate a Polish REGON (9- or 14-digit business registry number) |
| `generate_peppol_invoice` | Generate a Peppol BIS 3.0 / EN 16931 UBL 2.1 invoice |

## Installation

```bash
pip install mcp-ksef-pl
```

## Quick start

```json
{
  "mcpServers": {
    "ksef-pl": {
      "command": "uvx",
      "args": ["mcp-ksef-pl"],
      "env": {
        "KSEF_ENVIRONMENT": "test",
        "KSEF_SESSION_TOKEN": "<your-ksef-session-token>",
        "KSEF_NIP": "<your-nip>"
      }
    }
  }
}
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KSEF_ENVIRONMENT` | `test` | `production`, `test`, or `demo` |
| `KSEF_SESSION_TOKEN` | — | KSeF session token (from auth challenge-response flow) |
| `KSEF_NIP` | — | NIP of the entity submitting invoices |
| `KSEF_TIMEOUT` | `30` | HTTP timeout in seconds |

## KSeF authentication note

KSeF requires a signed XML challenge-response to obtain a session token before
invoices can be submitted. This step involves a qualified e-signature or a token
issued via the [MF portal](https://www.podatki.gov.pl/ksef/).  
Obtain the `sessionToken` externally and pass it via `KSEF_SESSION_TOKEN` or the
`session_token` parameter of `submit_invoice_to_ksef`.

## XSD schema

Full XSD validation requires the official schema from the Polish Ministry of Finance:

1. Download `FA_VAT_v1-0E.xsd` from https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/
2. Place it at `src/mcp_ksef_pl/schemas/FA_VAT_v1-0E.xsd`

Without the schema file, the validator runs business-rule checks only.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
pytest
```

## License

Apache-2.0
