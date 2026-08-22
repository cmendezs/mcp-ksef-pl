#!/usr/bin/env python3
"""Generate ``docs/TOOLS.md`` from the package's live MCP tool registry.

This script imports the package server module, finds its FastMCP instance,
introspects every registered tool, and renders a Markdown reference: one section
per tool with its description and a parameter table derived from the tool's JSON
Schema. It is self-contained and layout-agnostic (it auto-discovers the server
module under ``src/``), so the same file is copied unmodified into every package.

Run from the package root:

    python scripts/gen_tool_reference.py            # write docs/TOOLS.md
    python scripts/gen_tool_reference.py --check    # exit 1 if docs/TOOLS.md is stale

The output is deterministic (tools sorted by name, no timestamps) so ``--check``
can be used as a CI drift gate.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUTPUT = ROOT / "docs" / "TOOLS.md"


def _find_server_module() -> str:
    """Return the dotted path of the ``<package>.server`` module under ``src/``."""
    if not SRC.is_dir():
        raise SystemExit(f"no src/ directory found at {SRC}")
    for child in sorted(SRC.iterdir()):
        if (child / "server.py").is_file():
            return f"{child.name}.server"
    raise SystemExit("no <package>/server.py found under src/")


def _find_fastmcp(module: ModuleType) -> Any:
    """Locate the FastMCP instance exposed by a server module.

    Handles both the ``EInvoicingMCPServer`` wrapper (FastMCP is ``.mcp``) and a
    bare FastMCP instance assigned at module level.
    """
    from fastmcp import FastMCP

    for value in vars(module).values():
        if isinstance(value, FastMCP):
            return value
    for value in vars(module).values():
        inner = getattr(value, "mcp", None)
        if isinstance(inner, FastMCP):
            return inner
    raise SystemExit(f"no FastMCP instance found in {module.__name__}")


def _type_label(schema: dict[str, Any]) -> str:
    """Render a compact human-readable type from a JSON Schema fragment."""
    if not isinstance(schema, dict):
        return "any"
    if "type" in schema:
        t = schema["type"]
        if t == "array":
            items = schema.get("items", {})
            inner = _type_label(items) if items else "any"
            return f"array[{inner}]"
        return str(t)
    if "anyOf" in schema:
        parts = [_type_label(s) for s in schema["anyOf"] if s.get("type") != "null"]
        label = " | ".join(dict.fromkeys(parts)) or "any"
        if any(s.get("type") == "null" for s in schema["anyOf"]):
            label += " | null"
        return label
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "enum" in schema:
        return "enum"
    return "object"


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _render(server_name: str, tools: list[Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Tool reference — `{server_name}`")
    lines.append("")
    lines.append(
        "This file is generated from the MCP server's tool registry by "
        "`scripts/gen_tool_reference.py`. Do not edit it by hand; run the "
        "script instead."
    )
    lines.append("")
    lines.append(f"**Tools:** {len(tools)}")
    lines.append("")

    for tool in sorted(tools, key=lambda t: t.name):
        lines.append(f"## `{tool.name}`")
        lines.append("")
        description = (getattr(tool, "description", "") or "").strip()
        lines.append(description if description else "_No description provided._")
        lines.append("")

        schema = getattr(tool, "parameters", None) or {}
        properties: dict[str, Any] = schema.get("properties", {}) or {}
        required = set(schema.get("required", []) or [])

        if not properties:
            lines.append("_No parameters._")
            lines.append("")
            continue

        lines.append("| Parameter | Type | Required | Default | Description |")
        lines.append("|---|---|---|---|---|")
        for name, prop in properties.items():
            prop = prop or {}
            type_label = _type_label(prop)
            req = "yes" if name in required else "no"
            default = "" if "default" not in prop else f"`{prop['default']!r}`"
            desc = _escape(prop.get("description", ""))
            lines.append(f"| `{name}` | {type_label} | {req} | {default} | {desc} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _generate() -> str:
    sys.path.insert(0, str(SRC))
    module_name = _find_server_module()
    module = importlib.import_module(module_name)
    server = _find_fastmcp(module)
    tools = asyncio.run(server.list_tools())
    return _render(module_name.rsplit(".", 1)[0], tools)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 if docs/TOOLS.md differs from freshly generated output.",
    )
    args = parser.parse_args()

    content = _generate()

    if args.check:
        existing = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if existing != content:
            print(
                f"{OUTPUT.relative_to(ROOT)} is out of date. "
                "Run: python scripts/gen_tool_reference.py",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT.relative_to(ROOT)} is up to date.")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
