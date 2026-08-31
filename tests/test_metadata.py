"""Regression test for package metadata consistency."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import mcp_ksef_pl
from mcp_ksef_pl.generator import _SYSTEM_INFO

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_version_slot_consistency() -> None:
    pyproject = tomllib.loads((_PACKAGE_ROOT / "pyproject.toml").read_text())
    assert mcp_ksef_pl.__version__ == pyproject["project"]["version"], (
        f"__version__={mcp_ksef_pl.__version__} drifted from "
        f"pyproject={pyproject['project']['version']}"
    )


def test_server_json_version_matches_pyproject() -> None:
    pyproject = tomllib.loads((_PACKAGE_ROOT / "pyproject.toml").read_text())
    server = json.loads((_PACKAGE_ROOT / "server.json").read_text())
    expected = pyproject["project"]["version"]
    assert server["version"] == expected, (
        f"server.json version={server['version']} drifted from pyproject={expected}"
    )
    pkg_version = server["packages"][0]["version"]
    assert pkg_version == expected, (
        f"server.json packages[0].version={pkg_version} drifted from pyproject={expected}"
    )


def test_generator_system_info_matches_pyproject() -> None:
    """The <SystemInfo> element emitted into every FA(2)/FA(3) invoice must
    carry the real package version, not a stale hardcoded one (PL-SC-1)."""
    pyproject = tomllib.loads((_PACKAGE_ROOT / "pyproject.toml").read_text())
    expected = f"mcp-ksef-pl/{pyproject['project']['version']}"
    assert _SYSTEM_INFO == expected, f"_SYSTEM_INFO={_SYSTEM_INFO!r} drifted from {expected!r}"
