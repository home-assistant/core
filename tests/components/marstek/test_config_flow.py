"""Tests for the Marstek config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.marstek.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _mock_device() -> dict[str, str]:
    """Return a mocked discovery result."""
    return {
        "id": 0,
        "device_type": "ES5",
        "version": 1,
        "wifi_name": "TestWiFi",
        "ip": "192.168.1.101",
        "wifi_mac": "AA:BB:CC:DD:EE:FF",
        "ble_mac": "11:22:33:44:55:66",
        "mac": "AA:BB:CC:DD:EE:FF",
        "model": "ES5",
        "firmware": "1",
    }


def _mock_udp_client() -> AsyncMock:
    """Return a mocked Marstek UDP client."""
    client: AsyncMock = AsyncMock()
    client.async_setup = AsyncMock()
    client.async_cleanup = AsyncMock()
    client.discover_devices = AsyncMock()
    client.clear_discovery_cache = MagicMock()
    client._discovery_cache = []
    return client


async def test_step_user_success(hass: HomeAssistant) -> None:
    """Test the user step with a discovered device."""
    mock_client = _mock_udp_client()
    mock_client.discover_devices.return_value = [_mock_device()]

    with (
        patch(
            "homeassistant.components.marstek.config_flow.MarstekUDPClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.marstek.async_setup",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.marstek.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        selection_result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "0"}
        )
        assert selection_result["type"] == FlowResultType.CREATE_ENTRY
        assert selection_result["data"][CONF_HOST] == "192.168.1.101"
        assert selection_result["data"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"


async def test_step_user_no_devices(hass: HomeAssistant) -> None:
    """Test the user step when no devices are found."""
    mock_client = _mock_udp_client()
    mock_client.discover_devices.return_value = []

    with (
        patch(
            "homeassistant.components.marstek.config_flow.MarstekUDPClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.marstek.async_setup",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.marstek.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "no_devices_found"}


async def test_step_user_discovery_failure(hass: HomeAssistant) -> None:
    """Test the user step when discovery raises an exception."""
    mock_client = _mock_udp_client()
    mock_client.discover_devices.side_effect = TimeoutError
    mock_client._discovery_cache = []

    with (
        patch(
            "homeassistant.components.marstek.config_flow.MarstekUDPClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.marstek.async_setup",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.marstek.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "discovery_failed"}


async def test_step_user_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the device is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.101"}, unique_id="192.168.1.101"
    )
    existing_entry.add_to_hass(hass)

    mock_client = _mock_udp_client()
    mock_client.discover_devices.return_value = [_mock_device()]

    with (
        patch(
            "homeassistant.components.marstek.config_flow.MarstekUDPClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.marstek.async_setup",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.marstek.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM

        abort_result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "0"}
        )

        assert abort_result["type"] == FlowResultType.ABORT
        assert abort_result["reason"] == "already_configured"


async def test_step_user_retry_success(hass: HomeAssistant) -> None:
    """Test retry logic when the first attempt finds no devices."""
    device = _mock_device()

    mock_client = _mock_udp_client()
    mock_client.discover_devices.side_effect = [[], [device]]
    mock_client._discovery_cache = []

    with (
        patch(
            "homeassistant.components.marstek.config_flow.MarstekUDPClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.marstek.async_setup",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.marstek.async_setup_entry",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.marstek.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        assert mock_client.discover_devices.call_count == 2
        mock_client.clear_discovery_cache.assert_called_once()

        selection_result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "0"}
        )
        assert selection_result["type"] == FlowResultType.CREATE_ENTRY
