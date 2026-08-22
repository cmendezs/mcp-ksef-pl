# Contributing to mcp-ksef-pl

Thank you for your interest in contributing. This document explains the workflow
and expectations.

## Development setup

```bash
git clone https://github.com/cmendezs/mcp-ksef-pl.git
cd mcp-ksef-pl
uv sync --all-extras
```

## Running the test suite

```bash
uv run pytest
```

Run with verbose output:

```bash
uv run pytest -v
```

## Linting and type checking

```bash
uv run ruff check src/mcp_ksef_pl/ tests/ audit/
uv run ruff format --check src/mcp_ksef_pl/ tests/ audit/
uv run mypy src
```

To auto-fix lint issues:

```bash
uv run ruff check --fix src/mcp_ksef_pl/ tests/ audit/
uv run ruff format src/mcp_ksef_pl/ tests/ audit/
```

## Tool reference

The tool reference in `docs/TOOLS.md` is generated from the running MCP server.
If you add, remove, or change a tool or its parameters, regenerate it:

```bash
uv run python scripts/gen_tool_reference.py
```

The publish workflow regenerates it at release time, and `--check` mode reports
drift without writing:

```bash
uv run python scripts/gen_tool_reference.py --check
```

## Pull request checklist

- [ ] All tests pass (`pytest`)
- [ ] No lint errors (`ruff check`)
- [ ] No type errors (`mypy src`)
- [ ] New or changed behaviour is covered by tests
- [ ] Validation fixes reference the relevant rule ID (e.g. `FA(3)`)
- [ ] `docs/TOOLS.md` regenerated if any tool or parameter changed
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

## Commit style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add a new validation tool
fix: normalize party identifiers with leading zeros
docs: update README with configuration details
test: add fixture for a credit note
```

## Reporting issues

Please open an issue at https://github.com/cmendezs/mcp-ksef-pl/issues and include:

- The tool name and input you used
- The expected result
- The actual result (full error message or unexpected output)
- The national e-invoicing standard or rule ID involved, if known

Security issues follow a different path: see [SECURITY.md](SECURITY.md) and
report privately rather than in a public issue.
