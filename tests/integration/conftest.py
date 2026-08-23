"""Shared fixtures for KSeF integration tests.

These tests require a live KSeF test environment. They are skipped
automatically when the required environment variables are not set.
"""

import os

import pytest

from mcp_ksef_pl.config import KSeFSettings

_REQUIRED_VARS = ("KSEF_ENVIRONMENT", "KSEF_SESSION_TOKEN", "KSEF_NIP")


def _missing_vars() -> list[str]:
    return [v for v in _REQUIRED_VARS if not os.environ.get(v)]


pytestmark = pytest.mark.integration


@pytest.fixture(scope="session", autouse=True)
def _require_ksef_env() -> None:
    missing = _missing_vars()
    if missing:
        pytest.skip(f"KSeF integration tests require env vars: {', '.join(missing)}")


@pytest.fixture(scope="session")
def ksef_settings() -> KSeFSettings:
    return KSeFSettings()
