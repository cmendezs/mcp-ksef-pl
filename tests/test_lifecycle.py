"""Tests for KSeF lifecycle manager (HTTP mocked)."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_ksef_pl.config import KSeFEnvironment, KSeFSettings
from mcp_ksef_pl.lifecycle import KSeFLifecycleManager


@pytest.fixture
def test_settings() -> KSeFSettings:
    return KSeFSettings(
        environment=KSeFEnvironment.TEST,
        session_token="test-session-token-abc123",
        nip="5261040828",
    )


class TestKSeFLifecycleManager:
    @pytest.mark.asyncio
    async def test_submit_returns_reference(
        self, test_settings: KSeFSettings, sample_fa2_xml: str
    ) -> None:
        manager = KSeFLifecycleManager(test_settings)
        with patch.object(manager._client, "send_invoice", new_callable=AsyncMock) as mock_send, \
             patch.object(manager._client, "terminate_session", new_callable=AsyncMock):
            mock_send.return_value = {"elementReferenceNumber": "REF-2024-001"}
            reference = await manager.submit_document(
                sample_fa2_xml, {"terminate_after": True}
            )
        assert reference == "REF-2024-001"

    @pytest.mark.asyncio
    async def test_submit_without_token_raises(self) -> None:
        from mcp_einvoicing_core import PlatformError

        settings = KSeFSettings(environment=KSeFEnvironment.TEST, session_token="")
        manager = KSeFLifecycleManager(settings)
        with pytest.raises(PlatformError, match="session token"):
            await manager.submit_document("<Faktura/>", {})

    @pytest.mark.asyncio
    async def test_get_document_status(self, test_settings: KSeFSettings) -> None:
        manager = KSeFLifecycleManager(test_settings)
        mock_response = {"processingCode": 200, "processingDescription": "Accepted"}
        with patch.object(manager._client, "get_invoice_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = mock_response
            result = await manager.get_document_status("REF-2024-001")
        assert result["processingCode"] == 200

    @pytest.mark.asyncio
    async def test_search_documents(self, test_settings: KSeFSettings) -> None:
        manager = KSeFLifecycleManager(test_settings)
        mock_response = {"invoiceHeaderList": [{"ksefReferenceNumber": "REF-001"}]}
        with patch.object(manager._client, "query_invoices", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            results = await manager.search_documents(
                {"date_from": "2024-01-01", "date_to": "2024-01-31"}
            )
        assert len(results) == 1
        assert results[0]["ksefReferenceNumber"] == "REF-001"


@pytest.fixture
def sample_fa2_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Faktura xmlns="http://crd.gov.pl/wzor/2023/06/29/12648/">'
        "<Naglowek>"
        '<KodFormularza kodSystemowy="FA (2)" wersjaSchemy="1-0E">FA</KodFormularza>'
        "<WariantFormularza>2</WariantFormularza>"
        "<DataWytworzenieFa>2024-03-15T12:00:00Z</DataWytworzenieFa>"
        "<SystemInfo>mcp-ksef-pl/0.1.0</SystemInfo>"
        "</Naglowek>"
        "<Podmiot1><DaneIdentyfikacyjne><NIP>5261040828</NIP>"
        "<Nazwa>Ministerstwo Finansów</Nazwa></DaneIdentyfikacyjne></Podmiot1>"
        "<Podmiot2><DaneIdentyfikacyjne><NIP>5260250274</NIP>"
        "<Nazwa>Nabywca</Nazwa></DaneIdentyfikacyjne></Podmiot2>"
        "<Fa><KodWaluty>PLN</KodWaluty><P_1>2024-03-15</P_1>"
        "<P_2>FV/2024/001</P_2><P_13_1>2000.00</P_13_1>"
        "<P_14_1>460.00</P_14_1><P_15>2460.00</P_15>"
        "<Adnotacje><P_16>2</P_16><P_17>2</P_17><P_18>2</P_18>"
        "<P_18A>2</P_18A><P_23>2</P_23></Adnotacje>"
        "<FaWiersze><FaWiersz><NrWierszaFa>1</NrWierszaFa>"
        "<P_7>Usługi</P_7><P_8A>szt</P_8A><P_8B>10.0000</P_8B>"
        "<P_9A>200.00</P_9A><P_11>2000.00</P_11><P_12>23</P_12>"
        "</FaWiersz></FaWiersze></Fa>"
        "</Faktura>"
    )
