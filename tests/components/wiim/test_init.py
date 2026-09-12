"""Tests for the WiiM integration initialization."""

from socket import AddressFamily  # pylint: disable=no-name-in-module
from unittest.mock import AsyncMock, patch

import pytest
from wiim.exceptions import WiimDeviceException, WiimRequestException

from homeassistant.components.wiim.util import async_get_event_callback_host
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    mock_wiim_controller: AsyncMock,
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_wiim_controller")
async def test_shutdown_disconnects_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
) -> None:
    """Test the device is disconnected when Home Assistant stops."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_wiim_device.disconnect.assert_awaited_once_with()


@pytest.mark.usefixtures("mock_wiim_controller")
async def test_unload_entry_fails_when_platform_cannot_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry reports a failed unload when its platform cannot unload."""
    await setup_integration(hass, mock_config_entry)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD


@pytest.mark.parametrize(
    ("exc", "translation_key"),
    [
        pytest.param(
            WiimDeviceException("device init failed"),
            "device_setup_failed",
            id="device-error",
        ),
        pytest.param(
            WiimRequestException("http failure"),
            "http_api_request_failed",
            id="request-error",
        ),
    ],
)
async def test_setup_raises_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_controller: AsyncMock,
    exc: Exception,
    translation_key: str,
) -> None:
    """Test setup errors raise ConfigEntryNotReady with translation metadata."""
    with patch(
        "homeassistant.components.wiim.async_create_wiim_device",
        side_effect=exc,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders == {
        "host": "192.168.1.100"
    }


@pytest.mark.usefixtures("mock_wiim_controller")
async def test_setup_uses_route_to_device_for_event_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    mock_local_ip: AsyncMock,
) -> None:
    """Test the callback address is resolved from the route to the device."""
    await setup_integration(hass, mock_config_entry)

    mock_local_ip.assert_awaited_once_with(
        "http://192.168.1.100:49152/description.xml", hass.loop
    )
    assert (
        mock_wiim_device.create_mock.await_args.kwargs["local_host"] == "192.168.1.10"
    )


@pytest.mark.parametrize(
    ("family", "local_ip"),
    [
        (AddressFamily.AF_INET, "192.168.1.10"),
        (AddressFamily.AF_INET6, "2001:db8::5"),
    ],
)
async def test_event_callback_host_preserves_address_family(
    hass: HomeAssistant,
    mock_local_ip: AsyncMock,
    family: AddressFamily,
    local_ip: str,
) -> None:
    """Test the resolved address is used as-is for both IPv4 and IPv6."""
    mock_local_ip.return_value = (family, local_ip)

    assert (
        await async_get_event_callback_host(
            hass, "http://192.168.1.100:49152/description.xml"
        )
        == local_ip
    )


async def test_event_callback_host_falls_back_to_source_ip(
    hass: HomeAssistant,
    mock_local_ip: AsyncMock,
) -> None:
    """Test an unroutable device falls back to the announced source address."""
    mock_local_ip.side_effect = OSError("network is unreachable")

    with patch(
        "homeassistant.components.wiim.util.async_get_source_ip",
        return_value="192.168.1.10",
    ) as mock_source_ip:
        assert (
            await async_get_event_callback_host(
                hass, "http://192.168.1.100:49152/description.xml"
            )
            == "192.168.1.10"
        )

    mock_source_ip.assert_awaited_once_with(hass, target_ip="192.168.1.100")


@pytest.mark.usefixtures("mock_wiim_controller")
async def test_setup_retries_when_no_local_address(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_local_ip: AsyncMock,
) -> None:
    """Test setup retries when no local address can be determined."""
    mock_local_ip.side_effect = OSError("network is unreachable")

    with patch(
        "homeassistant.components.wiim.util.async_get_source_ip",
        side_effect=HomeAssistantError("no enabled IPv4 addresses"),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "callback_host_unavailable"
    assert mock_config_entry.error_reason_translation_placeholders is None
