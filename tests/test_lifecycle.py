"""Tests for KSeF v2 lifecycle manager (HTTP mocked)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_ksef_pl.config import KSeFEnvironment, KSeFSettings
from mcp_ksef_pl.lifecycle import (
    KSeFClient,
    KSeFLifecycleManager,
    _pick_encryption_cert,
    _to_iso_datetime,
)


@pytest.fixture
def test_settings() -> KSeFSettings:
    return KSeFSettings(
        environment=KSeFEnvironment.TEST,
        session_token="test-access-token-abc123",
        nip="5261040828",
    )


@pytest.fixture
def sample_fa3_xml() -> str:
    # Minimal FA(3) XML — uses the correct FA(3) namespace and header structure.
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">'
        "<Naglowek>"
        '<KodFormularza kodSystemowy="FA (3)" wersjaSchemy="1-0E">FA</KodFormularza>'
        "<WariantFormularza>3</WariantFormularza>"
        "<DataWytworzeniaFa>2026-03-15T12:00:00Z</DataWytworzeniaFa>"
        "<SystemInfo>mcp-ksef-pl/0.1.0</SystemInfo>"
        "</Naglowek>"
        "<Podmiot1><DaneIdentyfikacyjne><NIP>5261040828</NIP>"
        "<Nazwa>Ministerstwo Finansów</Nazwa></DaneIdentyfikacyjne></Podmiot1>"
        "<Podmiot2><DaneIdentyfikacyjne><NIP>5260250274</NIP>"
        "<Nazwa>Nabywca</Nazwa></DaneIdentyfikacyjne>"
        "<JST>2</JST><GV>2</GV></Podmiot2>"
        "<Fa><KodWaluty>PLN</KodWaluty><P_1>2026-03-15</P_1>"
        "<P_2>FV/2026/001</P_2><P_13_1>2000.00</P_13_1>"
        "<P_14_1>460.00</P_14_1><P_15>2460.00</P_15>"
        "<Adnotacje><P_16>2</P_16><P_17>2</P_17><P_18>2</P_18>"
        "<P_18A>2</P_18A>"
        "<Zwolnienie><P_19N>1</P_19N></Zwolnienie>"
        "<NoweSrodkiTransportu><P_22N>1</P_22N></NoweSrodkiTransportu>"
        "<P_23>2</P_23>"
        "<PMarzy><P_PMarzyN>1</P_PMarzyN></PMarzy>"
        "</Adnotacje>"
        "<RodzajFaktury>VAT</RodzajFaktury>"
        "<FaWiersz><NrWierszaFa>1</NrWierszaFa>"
        "<P_7>Usługi</P_7><P_8A>szt</P_8A><P_8B>10.0000</P_8B>"
        "<P_9A>200.00</P_9A><P_11>2000.00</P_11><P_12>23</P_12>"
        "</FaWiersz></Fa>"
        "</Faktura>"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestPickEncryptionCert:
    def test_picks_symmetric_key_cert(self) -> None:
        certs = [
            {"certificate": "cert1==", "usage": ["KsefTokenEncryption"]},
            {"certificate": "cert2==", "usage": ["SymmetricKeyEncryption"]},
        ]
        assert _pick_encryption_cert(certs) == "cert2=="

    def test_raises_when_none_found(self) -> None:
        from mcp_einvoicing_core import PlatformError

        certs = [{"certificate": "cert1==", "usage": ["KsefTokenEncryption"]}]
        with pytest.raises(PlatformError, match="SymmetricKeyEncryption"):
            _pick_encryption_cert(certs)

    def test_raises_on_empty_list(self) -> None:
        from mcp_einvoicing_core import PlatformError

        with pytest.raises(PlatformError):
            _pick_encryption_cert([])


class TestToIsoDatetime:
    def test_date_only_start(self) -> None:
        assert _to_iso_datetime("2026-01-15", end=False) == "2026-01-15T00:00:00+00:00"

    def test_date_only_end(self) -> None:
        assert _to_iso_datetime("2026-01-15", end=True) == "2026-01-15T23:59:59+00:00"

    def test_full_iso_passthrough(self) -> None:
        dt = "2026-01-15T12:30:00+00:00"
        assert _to_iso_datetime(dt, end=False) == dt

    def test_z_suffix_passthrough(self) -> None:
        dt = "2026-01-15T12:30:00Z"
        assert _to_iso_datetime(dt, end=False) == dt

    def test_negative_offset_passthrough(self) -> None:
        dt = "2026-01-15T12:30:00-05:00"
        assert _to_iso_datetime(dt, end=False) == dt

    def test_naive_datetime_gets_utc_offset(self) -> None:
        """PL-TZ-1: a 'T'-bearing value with no offset is assumed UTC."""
        assert _to_iso_datetime("2026-01-15T12:30:00", end=False) == "2026-01-15T12:30:00+00:00"


class TestKSeFClientRequest:
    @pytest.mark.asyncio
    async def test_logs_x_system_warning_header(
        self, test_settings: KSeFSettings, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = KSeFClient(test_settings)
        fake_response = MagicMock()
        fake_response.headers = {"X-System-Warning": "deprecated field used"}

        with (
            patch(
                "mcp_einvoicing_core.http_client.BaseEInvoicingClient._request",
                new_callable=AsyncMock,
                return_value=fake_response,
            ),
            caplog.at_level("WARNING"),
        ):
            response = await client._request("GET", "/limits/context")

        assert response is fake_response
        assert "deprecated field used" in caplog.text

    @pytest.mark.asyncio
    async def test_no_warning_header_is_silent(
        self, test_settings: KSeFSettings, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = KSeFClient(test_settings)
        fake_response = MagicMock()
        fake_response.headers = {}

        with (
            patch(
                "mcp_einvoicing_core.http_client.BaseEInvoicingClient._request",
                new_callable=AsyncMock,
                return_value=fake_response,
            ),
            caplog.at_level("WARNING"),
        ):
            await client._request("GET", "/limits/context")

        assert "X-System-Warning" not in caplog.text

    @pytest.mark.asyncio
    async def test_reraises_ksef_structured_error_from_response_body(
        self, test_settings: KSeFSettings
    ) -> None:
        """PL-ERR-1: PlatformError.response_body (core v1.28.0) makes this reachable."""
        from mcp_einvoicing_core import PlatformError

        client = KSeFClient(test_settings)
        upstream = PlatformError(
            status_code=400,
            message="HTTP error 400",
            response_body=b'{"exceptionCode": "AUTH_001", "message": "invalid token"}',
        )

        with patch(
            "mcp_einvoicing_core.http_client.BaseEInvoicingClient._request",
            new_callable=AsyncMock,
            side_effect=upstream,
        ):
            with pytest.raises(PlatformError, match=r"\[AUTH_001\] invalid token"):
                await client._request("GET", "/limits/context")

    @pytest.mark.asyncio
    async def test_reraises_unchanged_when_no_response_body(
        self, test_settings: KSeFSettings
    ) -> None:
        from mcp_einvoicing_core import PlatformError

        client = KSeFClient(test_settings)
        upstream = PlatformError(status_code=500, message="HTTP error 500")

        with patch(
            "mcp_einvoicing_core.http_client.BaseEInvoicingClient._request",
            new_callable=AsyncMock,
            side_effect=upstream,
        ):
            with pytest.raises(PlatformError, match="HTTP error 500") as exc_info:
                await client._request("GET", "/limits/context")
        assert exc_info.value is upstream


# ---------------------------------------------------------------------------
# KSeFLifecycleManager — submit
# ---------------------------------------------------------------------------


class TestSubmitDocument:
    @pytest.mark.asyncio
    async def test_submit_returns_compound_reference(
        self, test_settings: KSeFSettings, sample_fa3_xml: str
    ) -> None:
        manager = KSeFLifecycleManager(test_settings)

        # Build a minimal fake RSA public key that satisfies load_mf_public_key.
        # We mock the entire _encryption pipeline to avoid needing a real cert.
        fake_envelope = MagicMock()
        fake_envelope.encrypted_symmetric_key = "encKey=="
        fake_envelope.initialization_vector = "iv=="
        fake_envelope.build_send_payload.return_value = {
            "invoiceHash": "abc==",
            "invoiceSize": 100,
            "encryptedInvoiceHash": "def==",
            "encryptedInvoiceSize": 128,
            "encryptedInvoiceContent": "ghi==",
        }

        fake_certs = [{"certificate": "CERT==", "usage": ["SymmetricKeyEncryption"]}]

        with (
            patch.object(
                manager._client,
                "get_public_key_certificates",
                new_callable=AsyncMock,
                return_value=fake_certs,
            ),
            patch(
                "mcp_ksef_pl.lifecycle.load_mf_public_key",
                return_value=MagicMock(),
            ),
            patch(
                "mcp_ksef_pl.lifecycle.InvoiceEnvelope",
                return_value=fake_envelope,
            ),
            patch.object(
                manager._client,
                "open_online_session",
                new_callable=AsyncMock,
                return_value="SESSION-REF-001",
            ),
            patch.object(
                manager._client,
                "send_invoice_to_session",
                new_callable=AsyncMock,
                return_value="INVOICE-REF-001",
            ),
            patch.object(
                manager._client,
                "close_online_session",
                new_callable=AsyncMock,
            ),
        ):
            result = await manager.submit_document(sample_fa3_xml, {})

        assert result.session_ref == "SESSION-REF-001"
        assert result.invoice_ref == "INVOICE-REF-001"
        assert result.compound_id == "SESSION-REF-001:INVOICE-REF-001"

    @pytest.mark.asyncio
    async def test_submit_without_token_raises(self) -> None:
        from mcp_einvoicing_core import PlatformError

        settings = KSeFSettings(environment=KSeFEnvironment.TEST, session_token="")
        manager = KSeFLifecycleManager(settings)
        with pytest.raises(PlatformError, match="AccessToken"):
            await manager.submit_document("<Faktura/>", {})

    @pytest.mark.asyncio
    async def test_submit_session_close_failure_is_non_fatal(
        self, test_settings: KSeFSettings, sample_fa3_xml: str
    ) -> None:
        manager = KSeFLifecycleManager(test_settings)

        fake_envelope = MagicMock()
        fake_envelope.encrypted_symmetric_key = "encKey=="
        fake_envelope.initialization_vector = "iv=="
        fake_envelope.build_send_payload.return_value = {
            "invoiceHash": "abc==",
            "invoiceSize": 100,
            "encryptedInvoiceHash": "def==",
            "encryptedInvoiceSize": 128,
            "encryptedInvoiceContent": "ghi==",
        }

        with (
            patch.object(
                manager._client,
                "get_public_key_certificates",
                new_callable=AsyncMock,
                return_value=[{"certificate": "CERT==", "usage": ["SymmetricKeyEncryption"]}],
            ),
            patch("mcp_ksef_pl.lifecycle.load_mf_public_key", return_value=MagicMock()),
            patch("mcp_ksef_pl.lifecycle.InvoiceEnvelope", return_value=fake_envelope),
            patch.object(
                manager._client,
                "open_online_session",
                new_callable=AsyncMock,
                return_value="SESSION-001",
            ),
            patch.object(
                manager._client,
                "send_invoice_to_session",
                new_callable=AsyncMock,
                return_value="INV-001",
            ),
            patch.object(
                manager._client,
                "close_online_session",
                new_callable=AsyncMock,
                side_effect=Exception("network timeout"),
            ),
        ):
            result = await manager.submit_document(sample_fa3_xml, {})

        # Session close failed but we still get the compound reference.
        assert result.session_ref == "SESSION-001"
        assert result.invoice_ref == "INV-001"
        assert result.compound_id == "SESSION-001:INV-001"


# ---------------------------------------------------------------------------
# KSeFLifecycleManager — status
# ---------------------------------------------------------------------------


class TestGetDocumentStatus:
    @pytest.mark.asyncio
    async def test_compound_ref_calls_invoice_status(self, test_settings: KSeFSettings) -> None:
        manager = KSeFLifecycleManager(test_settings)
        expected = {"status": {"code": 200, "description": "Accepted"}}

        with patch.object(
            manager._client,
            "get_invoice_status",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_status:
            result = await manager.get_document_status("SESSION-001:INV-001")

        mock_status.assert_called_once_with("SESSION-001", "INV-001")
        assert result == expected

    @pytest.mark.asyncio
    async def test_session_only_ref_calls_session_status(self, test_settings: KSeFSettings) -> None:
        manager = KSeFLifecycleManager(test_settings)
        expected = {"status": "processed", "invoiceCount": 1}

        with patch.object(
            manager._client,
            "get_session_status",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_status:
            result = await manager.get_document_status("SESSION-001")

        mock_status.assert_called_once_with("SESSION-001")
        assert result == expected


# ---------------------------------------------------------------------------
# KSeFLifecycleManager — search
# ---------------------------------------------------------------------------


class TestSearchDocuments:
    @pytest.mark.asyncio
    async def test_search_builds_v2_payload(self, test_settings: KSeFSettings) -> None:
        manager = KSeFLifecycleManager(test_settings)
        mock_response = {"invoices": [{"ksefNumber": "REF-001"}], "hasMore": False}

        with patch.object(
            manager._client,
            "query_invoices",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_query:
            results = await manager.search_documents(
                {
                    "date_from": "2026-01-01",
                    "date_to": "2026-01-31",
                    "subject_type": "Subject2",
                    "date_type": "Issue",
                }
            )

        called_payload = mock_query.call_args[0][0]
        assert called_payload["subjectType"] == "Subject2"
        assert called_payload["dateRange"]["dateType"] == "Issue"
        assert called_payload["dateRange"]["from"] == "2026-01-01T00:00:00+00:00"
        assert called_payload["dateRange"]["to"] == "2026-01-31T23:59:59+00:00"
        assert len(results) == 1
        assert results[0]["ksefNumber"] == "REF-001"

    @pytest.mark.asyncio
    async def test_search_defaults(self, test_settings: KSeFSettings) -> None:
        manager = KSeFLifecycleManager(test_settings)

        with patch.object(
            manager._client,
            "query_invoices",
            new_callable=AsyncMock,
            return_value={"invoices": []},
        ) as mock_query:
            await manager.search_documents({})

        payload = mock_query.call_args[0][0]
        assert payload["subjectType"] == "Subject1"
        assert payload["dateRange"]["dateType"] == "Invoicing"
