"""Tests for Span Panel config flow validation helpers."""

from __future__ import annotations

import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from span_panel_api import DetectionResult, V2AuthResponse, V2StatusInfo
from span_panel_api.exceptions import SpanPanelConnectionError

from homeassistant.components.span_panel.config_flow_validation import (
    check_fqdn_tls_ready,
    is_fqdn,
    validate_host,
    validate_ipv4_address,
    validate_v2_passphrase,
    validate_v2_proximity,
)

MOCK_V2_AUTH = V2AuthResponse(
    access_token="v2-token-abc",
    token_type="bearer",
    iat_ms=1700000000000,
    ebus_broker_host="192.168.1.100",
    ebus_broker_mqtts_port=8883,
    ebus_broker_ws_port=8080,
    ebus_broker_wss_port=8443,
    ebus_broker_username="span-user",
    ebus_broker_password="mqtt-secret",
    hostname="span-panel.local",
    serial_number="SPAN-V2-001",
    hop_passphrase="correct-horse-battery-staple",
)


@pytest.mark.asyncio
async def test_validate_host_returns_true_for_supported_versions() -> None:
    """Supported API versions should count as valid hosts."""
    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ) as mock_get_client,
        patch(
            "homeassistant.components.span_panel.config_flow_validation.detect_api_version",
            return_value=DetectionResult(
                api_version="v2",
                status_info=V2StatusInfo(
                    serial_number="SPAN-V2-001", firmware_version="2.0.0"
                ),
            ),
        ) as mock_detect,
    ):
        assert await validate_host(hass, "panel.example.com", port=8080) is True

    mock_get_client.assert_called_once_with(hass, verify_ssl=False)
    mock_detect.assert_awaited_once_with(
        "panel.example.com", port=8080, httpx_client=fake_client
    )


@pytest.mark.asyncio
async def test_validate_host_returns_false_on_detection_error() -> None:
    """Detection failures should be treated as invalid hosts."""
    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.detect_api_version",
            side_effect=SpanPanelConnectionError("boom"),
        ),
    ):
        assert await validate_host(hass, "panel.example.com") is False


@pytest.mark.asyncio
async def test_validate_host_returns_false_when_probe_failed() -> None:
    """Transport/probe failures must not count as a reachable v1 host."""
    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.detect_api_version",
            return_value=DetectionResult(
                api_version="v1",
                status_info=None,
                probe_failed=True,
            ),
        ),
    ):
        assert await validate_host(hass, "panel.example.com") is False


@pytest.mark.asyncio
async def test_validate_host_returns_true_for_v1_when_http_response_received() -> None:
    """A real v1-only panel (non-200 on v2 status) should still validate as reachable."""
    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.detect_api_version",
            return_value=DetectionResult(
                api_version="v1",
                status_info=None,
                probe_failed=False,
            ),
        ),
    ):
        assert await validate_host(hass, "panel.example.com") is True


def test_validate_ipv4_and_fqdn_classification() -> None:
    """IPv4 and FQDN helpers should classify host formats correctly."""
    assert validate_ipv4_address("192.168.1.10") is True
    assert validate_ipv4_address("panel.example.com") is False

    assert is_fqdn("panel.example.com") is True
    assert is_fqdn("192.168.1.10") is False
    assert is_fqdn("2001:db8::1") is False
    assert is_fqdn("span-panel.local") is False
    assert is_fqdn("span-panel.local.") is False
    assert is_fqdn("panel") is False


@pytest.mark.asyncio
async def test_validate_v2_helpers_delegate_register_v2() -> None:
    """Passphrase and proximity helpers should delegate to register_v2."""
    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.register_v2",
            new=AsyncMock(return_value=MOCK_V2_AUTH),
        ) as mock_register,
    ):
        assert (
            await validate_v2_passphrase(
                hass, "panel.example.com", "passphrase", port=8080
            )
            == MOCK_V2_AUTH
        )
        assert (
            await validate_v2_proximity(hass, "panel.example.com", port=9090)
            == MOCK_V2_AUTH
        )

    assert mock_register.await_args_list[0].args == (
        "panel.example.com",
        "Home Assistant",
        "passphrase",
    )
    assert mock_register.await_args_list[0].kwargs == {
        "port": 8080,
        "httpx_client": fake_client,
    }
    assert mock_register.await_args_list[1].args == (
        "panel.example.com",
        "Home Assistant",
    )
    assert mock_register.await_args_list[1].kwargs == {
        "port": 9090,
        "httpx_client": fake_client,
    }


@pytest.mark.asyncio
async def test_check_fqdn_tls_ready_returns_false_when_ca_download_fails() -> None:
    """TLS readiness should fail fast when the CA certificate cannot be downloaded."""
    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.download_ca_cert",
            side_effect=SpanPanelConnectionError("no cert"),
        ) as mock_download,
    ):
        assert await check_fqdn_tls_ready(hass, "panel.example.com", 8883) is False

    mock_download.assert_awaited_once_with(
        "panel.example.com", port=80, httpx_client=fake_client
    )


@pytest.mark.asyncio
async def test_check_fqdn_tls_ready_forwards_custom_http_port() -> None:
    """TLS readiness should forward the provided HTTP port to CA download."""
    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.download_ca_cert",
            side_effect=SpanPanelConnectionError("no cert"),
        ) as mock_download,
    ):
        assert (
            await check_fqdn_tls_ready(hass, "panel.example.com", 8883, http_port=8080)
            is False
        )

    mock_download.assert_awaited_once_with(
        "panel.example.com", port=8080, httpx_client=fake_client
    )


@pytest.mark.asyncio
async def test_check_fqdn_tls_ready_returns_true_on_success() -> None:
    """TLS readiness should pass when the handshake succeeds."""

    class FakeLoop:
        async def run_in_executor(self, _executor, func):
            return func()

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeWrappedSocket(FakeSocket):
        pass

    class FakeSSLContext:
        def __init__(self, _protocol) -> None:
            self.check_hostname = False
            self.verify_mode = ssl.CERT_NONE

        def load_verify_locations(self, _path: str) -> None:
            return None

        def wrap_socket(self, _sock, server_hostname: str):
            assert server_hostname == "panel.example.com"
            return FakeWrappedSocket()

    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.download_ca_cert",
            new=AsyncMock(return_value="pem-data"),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.asyncio.get_running_loop",
            return_value=FakeLoop(),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.ssl.SSLContext",
            side_effect=FakeSSLContext,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.socket.create_connection",
            return_value=FakeSocket(),
        ),
    ):
        assert await check_fqdn_tls_ready(hass, "panel.example.com", 8883) is True


@pytest.mark.asyncio
async def test_check_fqdn_tls_ready_returns_false_on_ssl_error() -> None:
    """TLS readiness should fail when the hostname/cert handshake fails."""

    class FakeLoop:
        async def run_in_executor(self, _executor, func):
            return func()

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeSSLContext:
        def __init__(self, _protocol) -> None:
            self.check_hostname = False
            self.verify_mode = ssl.CERT_NONE

        def load_verify_locations(self, _path: str) -> None:
            return None

        def wrap_socket(self, _sock, server_hostname: str):
            raise ssl.SSLError(f"bad cert for {server_hostname}")

    hass = MagicMock()
    fake_client = MagicMock()
    with (
        patch(
            "homeassistant.components.span_panel.config_flow_validation.get_async_client",
            return_value=fake_client,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.download_ca_cert",
            new=AsyncMock(return_value="pem-data"),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.asyncio.get_running_loop",
            return_value=FakeLoop(),
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.ssl.SSLContext",
            side_effect=FakeSSLContext,
        ),
        patch(
            "homeassistant.components.span_panel.config_flow_validation.socket.create_connection",
            return_value=FakeSocket(),
        ),
    ):
        assert await check_fqdn_tls_ready(hass, "panel.example.com", 8883) is False
