# Security Policy

## Supported versions

Security fixes are applied to the latest published minor release only. Older
versions do not receive backported patches; upgrade to the current release to
stay supported.

| Version | Supported |
|---|---|
| 0.7.x | Yes |
| < 0.7.0 | No |

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub, not in a public
issue or pull request:

1. Go to the repository Security tab: https://github.com/cmendezs/mcp-ksef-pl/security
2. Select **Report a vulnerability** to open a private security advisory.
3. Describe the issue, the affected version, and a minimal reproduction.

You will receive an acknowledgement on a best-effort basis. This is a
volunteer-maintained open-source project, so response times vary; please allow
a reasonable window before any public disclosure.

## Scope and data-handling note

These tools generate, validate, and transmit fiscal documents. When you file a
report, include only synthetic data. Never attach real taxpayer identifiers,
production certificates, private keys, API tokens, or live credentials to an
advisory. Redact any such values from logs and reproductions before sharing.

## Out of scope

- Vulnerabilities in the underlying government platforms, PACs, OSEs, or Peppol
  access points that this package integrates with. Report those to the operator
  concerned.
- Findings that require a compromised local machine or a malicious dependency
  already installed in the runtime.
