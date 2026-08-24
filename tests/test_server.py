"""Smoke test: confirm the v0.8.0 core plugins register their tools."""

from mcp_ksef_pl import server


async def test_new_peppol_plugins_register_expected_tools() -> None:
    tools = await server.mcp.mcp.list_tools()
    names = {t.name for t in tools}

    assert {
        "peppol_directory_search",
        "validate_eusr_report",
        "validate_tsr_report",
        "validate_mls_message",
        "build_mls_message",
        "list_country_codes",
        "get_en16931_codelist_version",
    }.issubset(names)

    assert {"peppol-reporting", "peppol-mls", "en16931-codelists"}.issubset(
        set(server.mcp._plugins)
    )
