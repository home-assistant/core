"""Tests for the WiiM integration initialization."""

from socket import AddressFamily  # pylint: disable=no-name-in-module
from unittest.mock import AsyncMock, patch

import pytest
from wiim.exceptions import WiimDeviceException, WiimRequestException

from homeassistant.components.wiim.util import async_get_event_callback_host
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config

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


@pytest.mark.usefixtures("mock_wiim_device", "mock_wiim_controller")
async def test_setup_uses_route_to_device_for_event_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_local_ip: AsyncMock,
) -> None:
    """Test the callback address is resolved from the route to the device."""
    await setup_integration(hass, mock_config_entry, internal_url=None)

    mock_local_ip.assert_awaited_once_with(
        "http://192.168.1.100:49152/description.xml", hass.loop
    )


@pytest.mark.usefixtures("mock_wiim_device", "mock_wiim_controller")
async def test_setup_prefers_configured_internal_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_local_ip: AsyncMock,
) -> None:
    """Test a configured internal URL is used instead of the route to the device."""
    await setup_integration(
        hass, mock_config_entry, internal_url="http://192.168.1.50:8123"
    )

    mock_local_ip.assert_not_awaited()


@pytest.mark.parametrize("local_ip", ["192.168.1.10", "2001:db8::5"])
async def test_event_callback_host_preserves_address_family(
    hass: HomeAssistant,
    mock_local_ip: AsyncMock,
    local_ip: str,
) -> None:
    """Test the resolved address is used as-is for both IPv4 and IPv6."""
    mock_local_ip.return_value = (AddressFamily.AF_INET, local_ip)

    assert (
        await async_get_event_callback_host(
            hass, "http://192.168.1.100:49152/description.xml"
        )
        == local_ip
    )


async def test_setup_raises_config_entry_not_ready_when_no_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_controller: AsyncMock,
    mock_local_ip: AsyncMock,
) -> None:
    """Test a missing internal URL raises a translated ConfigEntryNotReady."""
    mock_local_ip.side_effect = OSError("network is unreachable")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "missing_homeassistant_url"
    assert mock_config_entry.error_reason_translation_placeholders is None


async def test_setup_no_url_after_core_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_device: AsyncMock,
    mock_wiim_controller: AsyncMock,
) -> None:
    """Test that setup succeeds once internal_url is configured."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://192.168.1.10:8123"}
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
