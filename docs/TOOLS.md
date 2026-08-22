# Tool reference — `mcp_ksef_pl`

This file is generated from the MCP server's tool registry by `scripts/gen_tool_reference.py`. Do not edit it by hand; run the script instead.

**Tools:** 24

## `check_document_type_id_in_codelist`

Check whether a (scheme, value) pair is a recognized Peppol document type identifier.

Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).
Searches all entries regardless of state, so a historical (deprecated
or removed) document type is still reported as found.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `scheme` | string | yes |  |  |
| `value` | string | yes |  |  |

## `check_participant_id_scheme_in_codelist`

Check whether a 4-digit ISO 6523 ICD code (e.g. "0208") is a recognized Peppol scheme.

Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `icd` | string | yes |  |  |

## `check_process_id_in_codelist`

Check whether a (scheme, value) pair is a recognized Peppol process identifier.

Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `scheme` | string | yes |  |  |
| `value` | string | yes |  |  |

## `generate_fa2_invoice`

Generate a KSeF-compliant FA(2) XML invoice from structured invoice data.

Returns the FA(2) XML string ready for submission to KSeF.
The seller's nip must be a Polish NIP (10 digits).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `invoice` | object | yes |  | EN 16931 invoice extended for KSeF FA(2)/FA(3) submission.  National extensions:   numer_ksef  — KSeF reference number, assigned by the platform post-clearance.                 Not present on the outbound document; populated from the                 clearance response and stored here for tracking.  The _allowed_profiles class variable is left as None because KSeF does not use EN 16931 GuidelineID URNs. The profile field should be set to the KSeF schema identifier or left to the generating tool's convention. |

## `generate_fa3_invoice`

Generate a KSeF-compliant FA(3) XML invoice from structured invoice data.

FA(3) is required for all new invoice submissions via KSeF API v2.
Use this tool, not generate_fa2_invoice, before calling submit_invoice_to_ksef.

The seller's nip must be a Polish NIP (10 digits).
The buyer's nip may be a Polish NIP, eu_vat_country/eu_vat_id for EU
cross-border, or neither (emits <BrakID>).

Use the optional `options` parameter to supply:
  - IPKSeF / LinkDoPlatnosci payment identifiers (PL-2.2)
  - Correction invoice reference (rodzaj_faktury=KOR + correction block) (PL-4.1)
  - Supporting document attachments (<Zalacznik>) (PL-2.3)
  - Additional buyer entities (<Podmiot3>) (PL-2.4)
  - Authorised representative (<PodmiotUpowazniony>) (PL-2.4)

Returns the FA(3) XML string ready for submit_invoice_to_ksef.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `invoice` | object | yes |  | EN 16931 invoice extended for KSeF FA(2)/FA(3) submission.  National extensions:   numer_ksef  — KSeF reference number, assigned by the platform post-clearance.                 Not present on the outbound document; populated from the                 clearance response and stored here for tracking.  The _allowed_profiles class variable is left as None because KSeF does not use EN 16931 GuidelineID URNs. The profile field should be set to the KSeF schema identifier or left to the generating tool's convention. |
| `options` | object | null | no | `None` |  |

## `generate_peppol_invoice`

Generate a Peppol BIS Billing 3.0 / EN 16931 UBL 2.1 XML invoice.

Use this for cross-border B2B invoicing via the Peppol network.
For domestic Polish invoicing, use generate_fa3_invoice instead.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `invoice` | object | yes |  | EN 16931 invoice extended for KSeF FA(2)/FA(3) submission.  National extensions:   numer_ksef  — KSeF reference number, assigned by the platform post-clearance.                 Not present on the outbound document; populated from the                 clearance response and stored here for tracking.  The _allowed_profiles class variable is left as None because KSeF does not use EN 16931 GuidelineID URNs. The profile field should be set to the KSeF schema identifier or left to the generating tool's convention. |

## `get_ksef_invoice_status`

Retrieve the processing status of a submitted KSeF invoice (API v2).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `reference_number` | string | yes |  | ("{sessionRef}:{invoiceRef}").  Pass just the sessionRef               to retrieve the overall session status instead. |

## `get_peppol_codelist_version`

Report the OpenPeppol eDEC code list release version(s) currently configured locally.

_No parameters._

## `list_document_type_ids`

List Peppol document type identifiers from the OpenPeppol eDEC code list.

Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `active_only` | boolean | no | `True` | When True (default), omit deprecated/removed entries. |

## `list_participant_id_schemes`

List Peppol participant identifier (ICD) schemes from the OpenPeppol eDEC code list.

Requires EINVOICING_PEPPOL_CODELIST_DIR to point at a local copy of
the eDEC "Participant Identifier Schemes" GeneriCode export (not
bundled with this package, no confirmed redistribution rights, see
`mcp_einvoicing_core.peppol.codelists` module docstring).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `active_only` | boolean | no | `True` | When True (default), omit deprecated/removed entries. |

## `list_process_ids`

List Peppol process identifiers from the OpenPeppol eDEC code list.

Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `active_only` | boolean | no | `True` | When True (default), omit deprecated/removed entries. |

## `list_spis_use_case_ids`

List Peppol SPIS use case identifiers from the OpenPeppol eDEC code list.

Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `active_only` | boolean | no | `True` | When True (default), omit deprecated/removed entries. |

## `parse_fa2_invoice`

Parse a KSeF FA(2) XML invoice into a structured dictionary.

Returns a nested dict with 'header', 'seller', 'buyer', 'invoice', and 'lines' keys.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | yes |  |  |

## `peppol_get_service_endpoint`

Fetch the AS4 endpoint for a Peppol participant's document type.

Resolves the SMP hostname via DNS, then fetches service metadata for
*document_type_id*. If the SMP returns a redirect, the result's
`redirect_url` is set and `endpoint_url` is None; callers must not
follow more than one redirect hop (SMP 1.4.0 §3.2).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `identifier` | string | yes |  | Peppol participant ID or adaptable national identifier. |
| `document_type_id` | string | no | `'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1'` | Peppol document type identifier URN (default: BIS Billing 3.0 invoice). |
| `environment` | string | no | `'production'` | "production" or "test". |

## `peppol_lookup_participant`

Check whether a business is registered on the Peppol network.

Performs a DNS-over-HTTPS U-NAPTR lookup followed by an SMP
service-group request to determine registration status and the list
of supported document type identifiers.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `identifier` | string | yes |  | Peppol participant ID ("<scheme>:<value>") or a bare national identifier this server knows how to adapt (e.g. a VAT number, if a national identifier adapter is configured). |
| `environment` | string | no | `'production'` | "production" or "test". |

## `peppol_send`

Send a UBL/CII invoice to a Peppol participant via AS4.

Looks up the recipient's AS4 endpoint (SMP), builds the ebMS3/AS4
envelope, and transmits it using the supplied signing credentials.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `invoice_xml_base64` | string | yes |  | Base64-encoded UBL or CII invoice XML. |
| `recipient_identifier` | string | yes |  | Peppol participant ID or adaptable national identifier of the receiver. |
| `sender_id` | string | yes |  | Peppol AP identifier of the sender. |
| `certificate_path` | string | yes |  | Path to the PEM-encoded signing certificate. |
| `private_key_path` | string | yes |  | Path to the PEM-encoded private key. |
| `private_key_password` | string | no | `''` | Optional password for the private key. |
| `document_type_id` | string | no | `'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1'` | Peppol document type identifier URN (default: BIS Billing 3.0 invoice). |
| `environment` | string | no | `'test'` | "production" or "test". |

## `resolve_peppol_dns`

Resolve the SMP hostname for a Peppol participant via DNS only.

Performs the raw U-NAPTR (SML) lookup without fetching the SMP
service group, useful for diagnosing whether a participant is
registered in the SML independently of SMP reachability.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `identifier` | string | yes |  | Peppol participant ID or adaptable national identifier. |
| `environment` | string | no | `'production'` | "production" or "test". |

## `search_ksef_invoices`

Query invoices stored in KSeF for a date range.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `date_from` | string | yes |  |  |
| `date_to` | string | yes |  |  |
| `subject_type` | string | no | `'Subject1'` | or 'SubjectAuthorized' (authorised representative). Case-insensitive;           normalized to the KSeF v2 PascalCase enum before submission. |

## `submit_invoice_to_ksef`

Submit a FA(3) XML invoice to the KSeF platform (API v2).

KSeF API v2 requires FA(3) format for submission.  Use generate_fa3_invoice
to produce FA(3) XML before calling this tool.

HUMAN-IN-THE-LOOP: Call without confirmation_token first to receive a
confirmation summary and token.  Show the summary to the user, then call
again with confirmation_token set to execute the actual submission.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | yes |  |  |
| `session_token` | string | no | `''` | Obtain via the challenge → authenticate → redeem flow:                       https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md |
| `session_token_expires_at` | string | no | `''` | A warning is logged if fewer than 60 seconds remain;                       submission is blocked if the token is already expired. |
| `confirmation_token` | string | no | `''` |  |

## `validate_fa2_invoice`

Validate a KSeF FA(2) XML invoice.

Runs XSD validation (when the official schema is present) and Polish
business-rule checks.  Returns a DocumentValidationResult with errors and warnings.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | yes |  |  |

## `validate_fa3_invoice`

Validate a KSeF FA(3) XML invoice before submission to KSeF API v2 (PL-6.2).

Runs XSD validation against specs/schemat_FA(3)_v1-0E.xsd (requires lxml)
and FA(3)-specific business-rule checks including namespace, mandatory
Adnotacje sub-elements, JST/GV flags, and the absence of the FA(2)
<FaWiersze> wrapper.

Call this after generate_fa3_invoice and before submit_invoice_to_ksef.
Returns a DocumentValidationResult with errors and warnings.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | yes |  |  |

## `validate_peppol_invoice`

Validate a Peppol BIS 3.0 / EN 16931 UBL 2.1 XML invoice.

Checks the CEN EN16931 base rules only (structural + arithmetic/totals,
~50 BR-* rules) via mcp-einvoicing-core's bundled Schematron validator.
Does NOT check the Peppol-specific overlay (profile/process ID
registration, EndpointID scheme, narrowed code lists) — the result's
metadata.scope is "en16931-base-only", and a warning is included. This is
not a full Peppol BIS3 conformance check; a document that passes may
still be rejected by a real Peppol Access Point. See
context-library/decisions/peppol-schematron-artifact.md for why.

Call this after generate_peppol_invoice to check the generated output.
Returns a DocumentValidationResult with errors and warnings.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | yes |  |  |

## `validate_polish_nip`

Validate a Polish NIP (tax identification number).

Applies the official 10-digit checksum algorithm.
Accepts NIP with or without dashes/spaces.

Returns {'valid': bool, 'nip': str, 'normalized': str}.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `nip` | string | yes |  |  |

## `validate_polish_regon`

Validate a Polish REGON (business registry number — 9 or 14 digits).

Returns {'valid': bool, 'regon': str, 'length': int}.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `regon` | string | yes |  |  |
