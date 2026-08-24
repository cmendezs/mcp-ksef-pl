# mcp-ksef-pl 🇵🇱

[English](README.md) | [Polski](README.pl.md)

<!-- mcp-name: io.github.cmendezs/mcp-ksef-pl -->

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
[![PyPI version](https://img.shields.io/pypi/v/mcp-ksef-pl.svg)](https://pypi.org/project/mcp-ksef-pl/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-ksef-pl.svg)](https://pypi.org/project/mcp-ksef-pl/)
[![mcp-ksef-pl MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-ksef-pl/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-ksef-pl)

Serwer MCP w Pythonie udostępniający narzędzia do polskiej **faktury elektronicznej** zgodnej z **KSeF (FA(2))** i **Peppol BIS Billing 3.0 / EN 16931**. Umożliwia agentom AI (Claude, IDE) generowanie, walidację i przesyłanie faktur do Krajowego Systemu e-Faktur (KSeF), a także weryfikację identyfikatorów podatkowych NIP i REGON.

## Zbudowano na

Ten pakiet jest zbudowany na bazie [**mcp-einvoicing-core**](https://github.com/cmendezs/mcp-einvoicing-core), wspólnej biblioteki bazowej dla europejskich serwerów MCP do fakturowania elektronicznego. Dostarcza ona klienta HTTP OAuth2, pamięć podręczną tokenów, modele danych, narzędzia do logowania i hierarchię wyjątków.

`mcp-einvoicing-core` jest instalowane automatycznie jako zależność, nie jest wymagany dodatkowy krok.

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

### Obsługa faktur FA(3) / FA(2)

| Narzędzie | Opis |
|-----------|------|
| `generate_fa3_invoice` | Generuje fakturę XML FA(3) zgodną z KSeF (wymagany format dla API v2) |
| `generate_fa2_invoice` | Generuje fakturę XML FA(2) zgodną z KSeF (format archiwalny, tylko do odczytu) |
| `validate_fa3_invoice` | Waliduje XML FA(3): walidacja XSD i reguły biznesowe specyficzne dla FA(3) |
| `validate_fa2_invoice` | Waliduje XML FA(2): walidacja XSD (jeśli schemat dostępny) i reguły biznesowe |
| `parse_fa2_invoice` | Parsuje XML FA(2) do słownika strukturalnego |

### Cykl życia w KSeF

| Narzędzie | Opis |
|-----------|------|
| `submit_invoice_to_ksef` | Przesyła fakturę FA(3) do platformy KSeF i zwraca numer referencyjny |
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
| `validate_peppol_invoice` | Waliduje fakturę UBL 2.1 Peppol względem podstawowych reguł Schematron CEN EN 16931 (zakres `en16931-base-only` — nie sprawdza reguł specyficznych dla nakładki Peppol) |

### Narzędzia sieci Peppol

Wyszukiwanie uczestnika Peppol, wyszukiwanie punktu usługowego, diagnostyka wyłącznie DNS, wysyłka AS4, wyszukiwanie w katalogu Peppol Directory oraz narzędzia list kodów OpenPeppol eDEC są dostarczane przez współdzielony wtyczkowy zestaw narzędzi Peppol z rdzenia (`mcp_einvoicing_core.peppol.tools.register_peppol_tools`), zamontowany w `server.py` z adapterem identyfikatora specyficznym dla Polski: goły NIP (np. `1234563218`) jest normalizowany do schematu Peppol `9945:<cyfry>` (`PL:VAT`, zgodnie z listą kodów OpenPeppol eDEC Participant Identifier Schemes); identyfikator już kwalifikowany schematem (np. `9945:1234563218`) przechodzi bez zmian. Użyj tych narzędzi, aby sprawdzić status rejestracji w PEF (polskim punkcie dostępowym Peppol dla fakturowania B2G w zamówieniach publicznych) przed użyciem `generate_peppol_invoice`.

`peppol_send` od `mcp-einvoicing-core` v1.20.0 podpisuje wychodzące wiadomości prawdziwym podpisem `wsse:Security` (wcześniej obliczanym i odrzucanym — zobacz CHANGELOG.md v0.8.0).

| Narzędzie | Opis |
|-----------|------|
| `peppol_lookup_participant` | Sprawdza, czy firma jest zarejestrowana w sieci Peppol; zwraca status rejestracji i obsługiwane typy dokumentów |
| `peppol_get_service_endpoint` | Pobiera punkt końcowy AS4 dla typu dokumentu uczestnika |
| `resolve_peppol_dns` | Diagnostyka wyłącznie DNS (SML), niezależna od dostępności SMP |
| `peppol_send` | Przesyła fakturę UBL/CII przez AS4 |
| `peppol_directory_search` | Przeszukuje publiczny katalog Peppol Directory według uczestnika, nazwy, kraju lub typu dokumentu |
| `list_participant_id_schemes`, `list_document_type_ids`, `list_process_ids`, `list_spis_use_case_ids` | Wyszukiwania w listach kodów OpenPeppol eDEC (wymagają `EINVOICING_PEPPOL_CODELIST_DIR`) |
| `check_document_type_id_in_codelist`, `check_process_id_in_codelist`, `check_participant_id_scheme_in_codelist`, `get_peppol_codelist_version` | Sprawdzenia list kodów OpenPeppol eDEC i raportowanie wersji |

Pełną dokumentację parametrów tych narzędzi znajdziesz w [README `mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core#readme).

---

### Narzędzia raportowania i statusu Peppol

Dodane w v0.8.0 poprzez trzy opcjonalne wtyczki rdzenia, montowane bezwarunkowo w `server.py`. Każda zwraca czytelny błąd przy wywołaniu (nie przy rejestracji), jeśli brakuje jej dodatku lub katalogu danych.

| Narzędzie | Wtyczka | Opis |
|-----------|---------|------|
| `validate_eusr_report` | `register_peppol_reporting_tools` | Waliduje End User Statistics Report (XSD, następnie Schematron). Wymaga dodatku `[xslt2]`. |
| `validate_tsr_report` | `register_peppol_reporting_tools` | Waliduje Transaction Statistics Report (XSD, następnie Schematron). Wymaga dodatku `[xslt2]`. |
| `validate_mls_message` | `register_peppol_mls_tools` | Waliduje dokument Message Level Status (podzbiór UBL `ApplicationResponse-2`). Wymaga dodatku `[xslt2]`. |
| `build_mls_message` | `register_peppol_mls_tools` | Buduje odpowiedź MLS na poziomie dokumentu. Wymaga dodatku `[xslt2]`. |
| 13 par `list_*`/`check_*`, `get_en16931_codelist_version` | `register_en16931_codelist_tools` | Wyszukiwania/sprawdzenia semantycznych list kodów EN 16931 (jednostki, kategorie VAT itd.). Wymagają `EINVOICING_EN16931_CODELIST_DIR`. |

Pełną dokumentację parametrów tych narzędzi znajdziesz w [README `mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core#readme).

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
| `KSEF_ENVIRONMENT` | `test` | Środowisko KSeF: `production` lub `test` |
| `KSEF_SESSION_TOKEN` | — | Token sesji KSeF (uzyskiwany przez przepływ challenge-response z MF) |
| `KSEF_NIP` | — | NIP podmiotu wysyłającego faktury |
| `KSEF_TIMEOUT` | `30` | Limit czasu żądań HTTP w sekundach |
| `KSEF_VERIFY_MF_KEY_PINNING` | `false` | Wymusza przypinanie SPKI SHA-256 dla certyfikatu szyfrującego MF. Nieaktywne, dopóki odciski palca nie zostaną skonfigurowane dla danego środowiska, nawet jeśli ustawione na `true` |
| `EINVOICING_PEPPOL_CODELIST_DIR` | — | Lokalny katalog zawierający własną kopię list kodów OpenPeppol eDEC, wymagany przez narzędzia list kodów Peppol (nie dołączony do tego pakietu; zobacz README `mcp-einvoicing-core`) |
| `EINVOICING_EN16931_CODELIST_DIR` | — | Lokalny katalog zawierający własną kopię semantycznych list kodów EN 16931 CEF "Digital Building Blocks", wymagany przez narzędzia list kodów EN 16931 (nie dołączony; zobacz README `mcp-einvoicing-core`) |

Narzędzia raportowania EUSR/TSR oraz MLS dodatkowo wymagają dodatku `[xslt2]` (`pip install "mcp-ksef-pl[xslt2]"`) do walidacji Schematron.

---

## 🔐 Uwierzytelnianie w KSeF

KSeF API v2 wykorzystuje wieloetapowy przepływ challenge/redeem do wydania tokenu AccessToken. Ten serwer MCP przyjmuje już uzyskany token i nie jest w stanie zautomatyzować kroku podpisywania (wymaga kwalifikowanego podpisu elektronicznego).

### Przepływ krok po kroku

1. **Rejestracja konta.** Zarejestruj się na portalu KSeF: https://ksef.mf.gov.pl/. Wybierz docelowe środowisko (test lub produkcja). Środowisko testowe: `https://ksef-test.mf.gov.pl/`.

2. **Pobranie wyzwania (challenge).** Wywołaj API KSeF, aby uzyskać kopertę XML z wyzwaniem:

   ```bash
   curl -s https://ksef-test.mf.gov.pl/auth/challenge \
     -H "Accept: application/json" \
     -d '{"contextIdentifier": {"type": "onip", "identifier": "TWOJ_NIP"}}' \
     -H "Content-Type: application/json"
   ```

   Odpowiedz zawiera ciag `challenge` oraz `timestamp`.

3. **Podpisanie wyzwania.** Zbuduj koperte XML `<InitSessionTokenRequest>` zawierajaca wyzwanie, nastepnie podpisz ja kwalifikowanym podpisem elektronicznym. Akceptowane narzedzia:

   - Dostawcy kwalifikowanych podpisow: KIR (Szafir), Certum, Sigillum
   - `podpis.gov.pl` (rzadowy portal do podpisywania)
   - Profil Zaufany: https://www.podatki.gov.pl/ksef/

   Przyklad z `xmlsec1` i certyfikatem PKCS#12:

   ```bash
   xmlsec1 --sign --pkcs12 twoj-certyfikat.p12 --pwd "haslo" \
     --output podpisane-wyzwanie.xml szablon-wyzwania.xml
   ```

4. **Przeslanie podpisanego wyzwania.** Wyslij podpisany XML, aby otrzymac referencje `authOperation`:

   ```bash
   curl -s https://ksef-test.mf.gov.pl/auth/xades-signature \
     -H "Content-Type: application/octet-stream" \
     --data-binary @podpisane-wyzwanie.xml
   ```

5. **Odbior AccessToken.** Wymien uwierzytelnioną operacje na AccessToken:

   ```bash
   curl -s https://ksef-test.mf.gov.pl/auth/token/redeem \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <referenceNumber-lub-token-authOperation-z-kroku-4>"
   ```

   Odpowiedz zawiera `accessToken.token` oraz `accessToken.context.referenceNumber`.

6. **Ustawienie tokenu.** Wyeksportuj token dla tego serwera MCP:

   ```bash
   export KSEF_SESSION_TOKEN="<AccessToken z kroku 5>"
   ```

   Token jest wazny przez okolo 2 godziny od wydania (zgodnie z dokumentacja MF). Po wygasnieciu powtorz kroki 2-5.

### Zrodla

- Dokumentacja techniczna KSeF: https://www.podatki.gov.pl/ksef/dokumentacja-techniczna-ksef/
- Specyfikacja uwierzytelniania (CIRFMF): https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md
- Specyfikacja sesji interaktywnej (CIRFMF): https://github.com/CIRFMF/ksef-docs/blob/main/sesja-interaktywna.md
- Komunikat o migracji na FA(3): `specs/ksef-v2-fa3-migration-announcement-20250630.pdf`

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
> `"KSEF_SESSION_TOKEN": "${KSEF_SESSION_TOKEN}"`, Kiro rozwiązuje zmienne środowiskowe
> powłoki przy uruchomieniu.

---

## 📋 Schemat XSD

Oficjalne schematy FA(2) i FA(3) są dołączone do pakietu (`src/mcp_ksef_pl/schemas/`)
i ładowane automatycznie przez `importlib.resources` — nie jest wymagane ręczne pobieranie
ani konfiguracja. `validate_fa2_invoice` i `validate_fa3_invoice` od razu wykonują pełną
walidację XSD dla każdej instalacji.

---

## 🧪 Testy

```bash
# Uruchom testy jednostkowe
uv run pytest tests/ -v
```

---

## Inne serwery MCP do e-fakturowania

| Kraj | Serwer |
|------|--------|
| 🌍 Globalny | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgia | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brazylia | [mcp-nfe-br](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 Francja | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Niemcy | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Włochy | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Polska | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Hiszpania | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

---

## 📄 Licencja

Ten projekt jest dystrybuowany na licencji **Apache 2.0**.
Szczegóły w pliku [LICENSE](LICENSE).

---
*Projekt utrzymywany przez cmendezs. W przypadku pytań dotyczących implementacji KSeF lub Peppol otwórz Issue.*
