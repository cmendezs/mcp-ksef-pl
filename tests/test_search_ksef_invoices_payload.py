"""PL-3.5: search_ksef_invoices subjectType must reach KSeF as the PascalCase enum."""

from unittest.mock import AsyncMock, patch

import pytest
from mcp_einvoicing_core import PlatformError

from mcp_ksef_pl.config import KSeFEnvironment, KSeFSettings
from mcp_ksef_pl.lifecycle import KSeFLifecycleManager


@pytest.fixture
def test_settings() -> KSeFSettings:
    return KSeFSettings(
        environment=KSeFEnvironment.TEST,
        session_token="test-access-token-abc123",
        nip="5261040828",
    )


class TestSubjectTypeNormalization:
    @pytest.mark.asyncio
    async def test_lowercase_subject1_normalizes_to_pascalcase(
        self, test_settings: KSeFSettings
    ) -> None:
        manager = KSeFLifecycleManager(test_settings)
        with patch.object(
            manager._client, "query_invoices",
            new_callable=AsyncMock, return_value={"invoices": []},
        ) as mock_query:
            await manager.search_documents({"subject_type": "subject1"})
        assert mock_query.call_args[0][0]["subjectType"] == "Subject1"

    @pytest.mark.asyncio
    async def test_subject_authorized_round_trips(
        self, test_settings: KSeFSettings
    ) -> None:
        manager = KSeFLifecycleManager(test_settings)
        with patch.object(
            manager._client, "query_invoices",
            new_callable=AsyncMock, return_value={"invoices": []},
        ) as mock_query:
            await manager.search_documents({"subject_type": "SubjectAuthorized"})
        assert mock_query.call_args[0][0]["subjectType"] == "SubjectAuthorized"

    @pytest.mark.asyncio
    async def test_lowercase_subject_authorized_normalizes(
        self, test_settings: KSeFSettings
    ) -> None:
        manager = KSeFLifecycleManager(test_settings)
        with patch.object(
            manager._client, "query_invoices",
            new_callable=AsyncMock, return_value={"invoices": []},
        ) as mock_query:
            await manager.search_documents({"subject_type": "subjectauthorized"})
        assert mock_query.call_args[0][0]["subjectType"] == "SubjectAuthorized"

    @pytest.mark.asyncio
    async def test_unrecognised_subject_type_raises(
        self, test_settings: KSeFSettings
    ) -> None:
        manager = KSeFLifecycleManager(test_settings)
        with pytest.raises(PlatformError, match="Unrecognised subject_type"):
            await manager.search_documents({"subject_type": "subject9"})

    @pytest.mark.asyncio
    async def test_default_is_subject1(self, test_settings: KSeFSettings) -> None:
        manager = KSeFLifecycleManager(test_settings)
        with patch.object(
            manager._client, "query_invoices",
            new_callable=AsyncMock, return_value={"invoices": []},
        ) as mock_query:
            await manager.search_documents({})
        assert mock_query.call_args[0][0]["subjectType"] == "Subject1"
