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

### FA(3) / FA(2) invoice handling

| Tool | Description |
|------|-------------|
| `generate_fa3_invoice` | Generates a KSeF-compliant FA(3) XML invoice (required for KSeF API v2 submissions) |
| `generate_fa2_invoice` | Generates a KSeF-compliant FA(2) XML invoice (legacy format, read-only use) |
| `validate_fa3_invoice` | Validates FA(3) XML: XSD validation and FA(3)-specific business rules |
| `validate_fa2_invoice` | Validates FA(2) XML: XSD validation (if the schema is available) and business rules |
| `parse_fa2_invoice` | Parses FA(2) XML into a structured dictionary |

### KSeF lifecycle

| Tool | Description |
|------|-------------|
| `submit_invoice_to_ksef` | Submits an FA(3) invoice to the KSeF platform and returns a reference number |
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
| `KSEF_ENVIRONMENT` | `test` | KSeF environment: `production` or `test` |
| `KSEF_SESSION_TOKEN` | — | KSeF session token (obtained through the challenge-response flow with MF) |
| `KSEF_NIP` | — | NIP of the entity submitting invoices |
| `KSEF_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `KSEF_VERIFY_MF_KEY_PINNING` | `false` | Enforce SPKI SHA-256 pinning on the MF encryption certificate. No-op until fingerprints are populated for the active environment, even when set to `true` |

---

## 🔐 KSeF authentication

KSeF API v2 uses a multi-step challenge/redeem flow to issue an AccessToken. This MCP server accepts an already-obtained token and cannot automate the signing step (it requires a qualified electronic signature).

### Step-by-step flow

1. **Account setup.** Register at the KSeF portal: https://ksef.mf.gov.pl/. Select the target environment (test or production). The test environment is at `https://ksef-test.mf.gov.pl/`.

2. **Request a challenge.** Call the KSeF API to obtain a challenge XML envelope:

   ```bash
   curl -s https://ksef-test.mf.gov.pl/auth/challenge \
     -H "Accept: application/json" \
     -d '{"contextIdentifier": {"type": "onip", "identifier": "YOUR_NIP"}}' \
     -H "Content-Type: application/json"
   ```

   The response contains a `challenge` string and a `timestamp`.

3. **Sign the challenge.** Build an `<InitSessionTokenRequest>` XML envelope containing the challenge, then sign it with your qualified e-signature. Accepted signing tools:

   - Qualified e-signature providers: KIR (Szafir), Certum, Sigillum
   - `podpis.gov.pl` (government signing portal)
   - Profil Zaufany (Trusted Profile): https://www.podatki.gov.pl/ksef/

   Example using `xmlsec1` with a PKCS#12 certificate:

   ```bash
   # Build the challenge XML (template at specs/przyklad-wyzwania.xml)
   xmlsec1 --sign --pkcs12 your-cert.p12 --pwd "password" \
     --output signed-challenge.xml challenge-template.xml
   ```

4. **Submit the signed challenge.** POST the signed XML to receive an `authOperation` reference:

   ```bash
   curl -s https://ksef-test.mf.gov.pl/auth/xades-signature \
     -H "Content-Type: application/octet-stream" \
     --data-binary @signed-challenge.xml
   ```

5. **Redeem the AccessToken.** Exchange the authenticated operation for an AccessToken:

   ```bash
   curl -s https://ksef-test.mf.gov.pl/auth/token/redeem \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <referenceNumber-or-authOperation-token-from-step-4>"
   ```

   The response contains `accessToken.token` and `accessToken.context.referenceNumber`.

6. **Set the token.** Export the token for this MCP server:

   ```bash
   export KSEF_SESSION_TOKEN="<the AccessToken from step 5>"
   ```

   The token is valid for approximately 2 hours from issuance (per MF documentation). After expiry, repeat steps 2-5.

### References

- KSeF technical documentation: https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/
- Authentication spec (CIRFMF): https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md
- Interactive session spec (CIRFMF): https://github.com/CIRFMF/ksef-docs/blob/main/sesja-interaktywna.md
- FA(3) migration announcement: `specs/ksef-v2-fa3-migration-announcement-20250630.pdf`

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

## 📋 XSD schema

The official FA(2) and FA(3) XSD schemas ship inside the package (`src/mcp_ksef_pl/schemas/`)
and are loaded automatically via `importlib.resources` — no manual download or configuration
is required. `validate_fa2_invoice` and `validate_fa3_invoice` run full XSD validation out
of the box for every installation.

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
