# mcp-ksef-pl 🇵🇱
<!-- mcp-name: io.github.cmendezs/mcp-ksef-pl -->

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
[![PyPI version](https://img.shields.io/pypi/v/mcp-ksef-pl.svg)](https://pypi.org/project/mcp-ksef-pl/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-ksef-pl.svg)](https://pypi.org/project/mcp-ksef-pl/)
[![mcp-ksef-pl MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-ksef-pl/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-ksef-pl)

Serwer MCP w Pythonie udostępniający narzędzia do polskiej **faktury elektronicznej** zgodnej z **KSeF (FA(2))** i **Peppol BIS Billing 3.0 / EN 16931**. Umożliwia agentom AI (Claude, IDE) generowanie, walidację i przesyłanie faktur do Krajowego Systemu e-Faktur (KSeF), a także weryfikację identyfikatorów podatkowych NIP i REGON.

**English:** This is a **Model Context Protocol (MCP)** server for **Polish electronic invoicing**. It implements the **KSeF FA(2)** national invoice format and the **Peppol BIS Billing 3.0 / EN 16931** cross-border format, enabling AI agents to generate, validate, submit, and query invoices via the Krajowy System e-Faktur (KSeF) platform, and to validate Polish tax identifiers (NIP, REGON).

## Built on

Ten pakiet jest zbudowany na bazie [**mcp-einvoicing-core**](https://github.com/cmendezs/mcp-einvoicing-core) — wspólnej biblioteki bazowej dla europejskich serwerów MCP do fakturowania elektronicznego. Dostarcza ona klienta HTTP OAuth2, pamięć podręczną tokenów, modele danych, narzędzia do logowania i hierarchię wyjątków.

`mcp-einvoicing-core` jest instalowane automatycznie jako zależność — nie jest wymagany dodatkowy krok.

---

## 🏗️ Architektura

Serwer pełni rolę inteligentnego interfejsu komunikacyjnego między agentem AI a platformą KSeF oraz siecią Peppol:

```text
[ System ERP / Aplikacja ] <--> [ Serwer MCP ] <--> [ KSeF (MF) / Sieć Peppol ]
          ^                           |
          |                           v
   [ Agent AI (Claude) ] <--- (FA(2) / EN 16931)
```

---

## 🛠️ Dostępne narzędzia

### Obsługa faktur FA(2)

| Narzędzie | Opis |
|-----------|------|
| `generate_fa2_invoice` | Generuje fakturę XML FA(2) zgodną z KSeF na podstawie danych wejściowych |
| `validate_fa2_invoice` | Waliduje XML FA(2) — walidacja XSD (jeśli schemat dostępny) i reguły biznesowe |
| `parse_fa2_invoice` | Parsuje XML FA(2) do słownika strukturalnego |

### Cykl życia w KSeF

| Narzędzie | Opis |
|-----------|------|
| `submit_invoice_to_ksef` | Przesyła fakturę FA(2) do platformy KSeF i zwraca numer referencyjny |
| `get_ksef_invoice_status` | Pobiera status przetwarzania faktury według numeru referencyjnego |
| `search_ksef_invoices` | Wyszukuje faktury w KSeF według zakresu dat i kierunku (sprzedawca/nabywca) |

### Walidacja identyfikatorów

| Narzędzie | Opis |
|-----------|------|
| `validate_polish_nip` | Waliduje NIP (10-cyfrowy numer identyfikacji podatkowej) algorytmem sumy kontrolnej |
| `validate_polish_regon` | Waliduje REGON (9- lub 14-cyfrowy numer ewidencyjny) algorytmem sumy kontrolnej |

### Peppol / EN 16931

| Narzędzie | Opis |
|-----------|------|
| `generate_peppol_invoice` | Generuje fakturę UBL 2.1 zgodną z Peppol BIS Billing 3.0 / EN 16931 |

---

## 🚀 Instalacja

### Przez PyPI (zalecane)

```bash
pip install mcp-ksef-pl
```

Lub bez wcześniejszej instalacji z `uvx`:

```bash
uvx mcp-ksef-pl
```

### Ze źródeł

```bash
git clone https://github.com/cmendezs/mcp-ksef-pl.git
cd mcp-ksef-pl
uv sync --all-extras
```

---

## ⚙️ Konfiguracja (zmienne środowiskowe)

| Zmienna | Domyślna | Opis |
|---------|----------|------|
| `KSEF_ENVIRONMENT` | `test` | Środowisko KSeF: `production`, `test` lub `demo` |
| `KSEF_SESSION_TOKEN` | — | Token sesji KSeF (uzyskiwany przez przepływ challenge-response z MF) |
| `KSEF_NIP` | — | NIP podmiotu wysyłającego faktury |
| `KSEF_TIMEOUT` | `30` | Limit czasu żądań HTTP w sekundach |

---

## 🔐 Uwierzytelnianie w KSeF

KSeF wymaga podpisanego XML (challenge-response) do uzyskania tokenu sesji. Podpisanie
wymaga kwalifikowanego podpisu elektronicznego lub poświadczeń z portalu MF i nie może
być zautomatyzowane przez ten serwer MCP. Token sesji należy uzyskać poza serwerem
i przekazać przez `KSEF_SESSION_TOKEN` lub parametr `session_token` narzędzia
`submit_invoice_to_ksef`.

Dokumentacja techniczna KSeF: https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/

---

## 🤖 Integracja z Claude Desktop

Dodaj poniższą konfigurację do pliku `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ksef-pl": {
      "command": "uvx",
      "args": ["mcp-ksef-pl"],
      "env": {
        "KSEF_ENVIRONMENT": "test",
        "KSEF_SESSION_TOKEN": "<twój-token-sesji-ksef>",
        "KSEF_NIP": "<twój-nip>"
      }
    }
  }
}
```

---

## ⌨️ Integracja z Cursor

Cursor obsługuje serwery MCP przez stdio. Dodaj konfigurację do:
- **Globalnie** (wszystkie projekty): `~/.cursor/mcp.json`
- **Projekt** (tylko to repozytorium): `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "ksef-pl": {
      "command": "uvx",
      "args": ["mcp-ksef-pl"],
      "env": {
        "KSEF_ENVIRONMENT": "test",
        "KSEF_SESSION_TOKEN": "<twój-token-sesji-ksef>",
        "KSEF_NIP": "<twój-nip>"
      }
    }
  }
}
```

Przeładuj okno Cursor (`Ctrl+Shift+P` → *Reload Window*) po zapisaniu zmian.

---

## 🪐 Integracja z Kiro

Kiro obsługuje serwery MCP przez dedykowany plik konfiguracyjny:
- **Globalnie**: `~/.kiro/settings/mcp.json`
- **Workspace**: `.kiro/settings/mcp.json`

```json
{
  "mcpServers": {
    "ksef-pl": {
      "command": "uvx",
      "args": ["mcp-ksef-pl"],
      "env": {
        "KSEF_ENVIRONMENT": "test",
        "KSEF_SESSION_TOKEN": "<twój-token-sesji-ksef>",
        "KSEF_NIP": "<twój-nip>"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

> **Wskazówka bezpieczeństwa**: zamiast wpisywać token wprost, użyj składni
> `"KSEF_SESSION_TOKEN": "${KSEF_SESSION_TOKEN}"` — Kiro rozwiązuje zmienne środowiskowe
> powłoki przy uruchomieniu.

---

## 📋 Schemat XSD (FA_VAT_v1-0E.xsd)

Pełna walidacja XSD wymaga oficjalnego schematu Ministerstwa Finansów.
Bez niego `validate_fa2_invoice` wykonuje wyłącznie reguły biznesowe.

1. Przejdź na stronę: https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/
2. Pobierz pakiet dokumentacji technicznej FA(2)
3. Umieść plik `FA_VAT_v1-0E.xsd` w katalogu `src/mcp_ksef_pl/schemas/`

Plik jest wykluczony z repozytorium (`.gitignore`) — należy go pobrać ręcznie.
Pomocniczy skrypt: `scripts/download_schemas.sh`

---

## 🧪 Testy

```bash
# Uruchom testy jednostkowe
uv run pytest tests/ -v
```

---

## Other e-invoicing MCP servers

| Country | Server |
|---------|--------|
| 🌍 Global | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgium | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇫🇷 France | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Germany | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italy | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Poland | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Spain | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

---

## 📄 Licencja

Ten projekt jest dystrybuowany na licencji **Apache 2.0**.
Szczegóły w pliku [LICENSE](LICENSE).

---
*Projekt utrzymywany przez cmendezs. W przypadku pytań dotyczących implementacji KSeF lub Peppol otwórz Issue.*
