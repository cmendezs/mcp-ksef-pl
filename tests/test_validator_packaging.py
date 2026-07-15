"""Guards PL-6.3: the FA(2)/FA(3) XSDs must always resolve via importlib.resources.

Without this guard, a future pyproject.toml edit or file move could silently
re-introduce the packaging miss where get_schema_path() returns None for
installed users, downgrading FA3Validator to loose regex checks.
"""

from importlib.resources import files


def test_fa2_schema_resolvable_via_importlib_resources() -> None:
    resource = files("mcp_ksef_pl.schemas").joinpath("schemat_FA(2)_v1-0E.xsd")
    assert resource.is_file()


def test_fa3_schema_resolvable_via_importlib_resources() -> None:
    resource = files("mcp_ksef_pl.schemas").joinpath("schemat_FA(3)_v1-0E.xsd")
    assert resource.is_file()


def test_fa2_validator_get_schema_path_not_none() -> None:
    from mcp_ksef_pl.validator import FA2Validator

    assert FA2Validator().get_schema_path() is not None


def test_fa3_validator_get_schema_path_not_none() -> None:
    from mcp_ksef_pl.validator import FA3Validator

    assert FA3Validator().get_schema_path() is not None
