# mcp-ksef-pl 🇵🇱

[English](README.md) | [Polski](README.pl.md)

<!-- mcp-name: io.github.cmendezs/mcp-ksef-pl -->

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
[![PyPI version](https://img.shields.io/pypi/v/mcp-ksef-pl.svg)](https://pypi.org/project/mcp-ksef-pl/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-ksef-pl.svg)](https://pypi.org/project/mcp-ksef-pl/)
[![mcp-ksef-pl MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-ksef-pl/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-ksef-pl)

A Python MCP server providing tools for Polish **electronic invoicing** compliant with **KSeF (FA(2))** and **Peppol BIS Billing 3.0 / EN 16931**. It enables AI agents (Claude, IDEs) to generate, validate, and submit invoices to the Krajowy System e-Faktur (KSeF), as well as validate Polish tax identifiers (NIP and REGON).

## Built on

This package is built on [**mcp-einvoicing-core**](https://github.com/cmendezs/mcp-einvoicing-core), the shared base library for European e-invoicing MCP servers. It provides an OAuth2 HTTP client, token cache, data models, logging utilities, and an exception hierarchy.

`mcp-einvoicing-core` is installed automatically as a dependency, no additional step is required.

---

## 🏗️ Architecture

The server acts as an intelligent communication interface between the AI agent and the KSeF platform and the Peppol network:

```text
[ ERP System / Application ] <--> [ MCP Server ] <--> [ KSeF (MF) / Peppol Network ]
          ^                           |
          |                           v
   [ AI Agent (Claude) ] <--- (FA(2) / EN 16931)
```

---

## 🛠️ Available tools

### FA(2) invoice handling

| Tool | Description |
|------|-------------|
| `generate_fa2_invoice` | Generates a KSeF-compliant FA(2) XML invoice from input data |
| `validate_fa2_invoice` | Validates FA(2) XML: XSD validation (if the schema is available) and business rules |
| `parse_fa2_invoice` | Parses FA(2) XML into a structured dictionary |

### KSeF lifecycle

| Tool | Description |
|------|-------------|
| `submit_invoice_to_ksef` | Submits an FA(2) invoice to the KSeF platform and returns a reference number |
| `get_ksef_invoice_status` | Retrieves the processing status of an invoice by its reference number |
| `search_ksef_invoices` | Searches invoices in KSeF by date range and direction (seller/buyer) |

### Identifier validation

| Tool | Description |
|------|-------------|
| `validate_polish_nip` | Validates a NIP (10-digit tax identification number) using a checksum algorithm |
| `validate_polish_regon` | Validates a REGON (9- or 14-digit registry number) using a checksum algorithm |

### Peppol / EN 16931

| Tool | Description |
|------|-------------|
| `generate_peppol_invoice` | Generates a UBL 2.1 invoice compliant with Peppol BIS Billing 3.0 / EN 16931 |

---

## 🚀 Installation

### Via PyPI (recommended)

```bash
pip install mcp-ksef-pl
```

Or without prior installation using `uvx`:

```bash
uvx mcp-ksef-pl
```

### From source

```bash
git clone https://github.com/cmendezs/mcp-ksef-pl.git
cd mcp-ksef-pl
uv sync --all-extras
```

---

## ⚙️ Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `KSEF_ENVIRONMENT` | `test` | KSeF environment: `production`, `test`, or `demo` |
| `KSEF_SESSION_TOKEN` | — | KSeF session token (obtained through the challenge-response flow with MF) |
| `KSEF_NIP` | — | NIP of the entity submitting invoices |
| `KSEF_TIMEOUT` | `30` | HTTP request timeout in seconds |

---

## 🔐 KSeF authentication

KSeF requires signed XML (challenge-response) to obtain a session token. Signing
requires a qualified electronic signature or credentials from the MF portal and cannot
be automated by this MCP server. The session token must be obtained outside the server
and passed via `KSEF_SESSION_TOKEN` or the `session_token` parameter of the
`submit_invoice_to_ksef` tool.

Technical documentation for KSeF: https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/

---

## 🤖 Claude Desktop integration

Add the following configuration to your `claude_desktop_config.json` file:

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

---

## ⌨️ Cursor integration

Cursor supports MCP servers via stdio. Add the configuration to:
- **Globally** (all projects): `~/.cursor/mcp.json`
- **Per project** (this repository only): `.cursor/mcp.json`

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

Reload the Cursor window (`Ctrl+Shift+P` → *Reload Window*) after saving changes.

---

## 🪐 Kiro integration

Kiro supports MCP servers through a dedicated configuration file:
- **Globally**: `~/.kiro/settings/mcp.json`
- **Workspace**: `.kiro/settings/mcp.json`

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
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

> **Security tip**: instead of entering the token directly, use the syntax
> `"KSEF_SESSION_TOKEN": "${KSEF_SESSION_TOKEN}"`, as Kiro resolves shell environment
> variables at startup.

---

## 📋 XSD schema (FA_VAT_v1-0E.xsd)

Full XSD validation requires the official schema from the Ministry of Finance.
Without it, `validate_fa2_invoice` only executes business rules.

1. Go to: https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/
2. Download the FA(2) technical documentation package
3. Place the `FA_VAT_v1-0E.xsd` file in the `src/mcp_ksef_pl/schemas/` directory

The file is excluded from the repository (`.gitignore`), it must be downloaded manually.
Helper script: `scripts/download_schemas.sh`

---

## 🧪 Tests

```bash
# Run unit tests
uv run pytest tests/ -v
```

---

## Other e-invoicing MCP servers

| Country | Server |
|---------|--------|
| 🌍 Global | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgium | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brazil | [mcp-nfe-br](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 France | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Germany | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italy | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Poland | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Spain | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

---

## 📄 License

This project is distributed under the **Apache 2.0** license.
See the [LICENSE](LICENSE) file for details.

---
*Project maintained by cmendezs. For questions about the KSeF or Peppol implementation, open an Issue.*
