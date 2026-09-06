#!/usr/bin/env python3
"""Generate ``docs/public/llms.txt`` from in-repo sources only.

This is the deterministic fallback/override for the curated top-level ``llms.txt`` — see
context-library/decisions/docs-site.md and context-library/templates/docs-site-template.md's
"llms.txt / llms-full.txt contract" section for why this exists alongside the
``starlight-llms-txt`` plugin's own ``/llms-full.txt`` output: the plugin's exact API and
maintenance status are [Unverified] from the environment this script was authored in, so the
curated index must not depend solely on it.

Reads only: ``pyproject.toml`` (name, description, version), ``server.json`` (registry id),
and ``README.md`` (nothing beyond confirming it exists). Never invents an identifier — every
value written here traces to one of those two files, matching the same sourcing rule
readme-template.md already states for client-integration JSON blocks.

Run from the package's ``docs/`` directory:

    python scripts/gen_llms_txt.py            # write public/llms.txt
    python scripts/gen_llms_txt.py --check    # exit 1 if public/llms.txt is stale

The output is deterministic (no timestamps) so ``--check`` can be used as a CI drift gate.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = DOCS_ROOT.parent
OUTPUT = DOCS_ROOT / "public" / "llms.txt"
PAGES_BASE = "https://cmendezs.github.io"


def _read_pyproject() -> dict[str, str]:
    path = PACKAGE_ROOT / "pyproject.toml"
    if not path.is_file():
        raise SystemExit(f"no pyproject.toml found at {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    name = project.get("name")
    description = project.get("description")
    version = project.get("version")
    if not name or not description:
        raise SystemExit("pyproject.toml [project] must set both name and description")
    return {"name": name, "description": description, "version": version or ""}


def _read_registry_id() -> str:
    path = PACKAGE_ROOT / "server.json"
    if not path.is_file():
        raise SystemExit(f"no server.json found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    registry_id = data.get("name")
    if not registry_id:
        raise SystemExit("server.json is missing the top-level 'name' (registry id) field")
    return registry_id


def _repo_name() -> str:
    # The package directory name matches the GitHub repo name for every package in this
    # workspace (e.g. mcp-einvoicing-de, mcp-cfdi-mx) — see CLAUDE.md's repository-layout
    # section. Deriving it this way avoids depending on `git remote` at generation time.
    return PACKAGE_ROOT.name


def _render(pyproject: dict[str, str], registry_id: str, repo: str) -> str:
    base = f"{PAGES_BASE}/{repo}/"
    lines: list[str] = []
    lines.append(f"# {pyproject['name']}")
    lines.append("")
    lines.append(f"> {pyproject['description']}")
    lines.append("")
    lines.append("## Docs")
    lines.append("")
    lines.append(
        f"- [Overview]({base}): the full README — what this server does, installation, configuration, available tools"
    )
    lines.append(f"- [Tools]({base}tools/): full MCP tool reference")
    lines.append(f"- [Changelog]({base}changelog/): version history")
    lines.append(f"- [Contributing]({base}contributing/): dev setup and PR checklist")
    lines.append(f"- [Security]({base}security/): vulnerability disclosure policy")
    lines.append("")
    lines.append("## Links")
    lines.append("")
    lines.append(f"- [PyPI](https://pypi.org/project/{pyproject['name']}/)")
    lines.append(
        f"- [MCP registry](https://registry.modelcontextprotocol.io/v0/servers?search={registry_id})"
    )
    lines.append(f"- [GitHub](https://github.com/cmendezs/{repo})")
    return "\n".join(lines).rstrip() + "\n"


def _generate() -> str:
    if not (PACKAGE_ROOT / "README.md").is_file():
        raise SystemExit(f"no README.md found at {PACKAGE_ROOT / 'README.md'}")
    pyproject = _read_pyproject()
    registry_id = _read_registry_id()
    repo = _repo_name()
    return _render(pyproject, registry_id, repo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 if public/llms.txt differs from freshly generated output.",
    )
    args = parser.parse_args()

    content = _generate()

    if args.check:
        existing = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if existing != content:
            print(
                f"{OUTPUT.relative_to(PACKAGE_ROOT)} is out of date. "
                "Run: python scripts/gen_llms_txt.py",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT.relative_to(PACKAGE_ROOT)} is up to date.")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(PACKAGE_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
