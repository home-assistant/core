"""Tests for the WiiM integration initialization."""

from unittest.mock import AsyncMock, patch

import pytest
from wiim.exceptions import WiimDeviceException, WiimRequestException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
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


async def test_setup_raises_config_entry_not_ready_when_no_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wiim_controller: AsyncMock,
) -> None:
    """Test a missing internal URL raises a translated ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "missing_homeassistant_url"
    assert mock_config_entry.error_reason_translation_placeholders is None


@pytest.mark.usefixtures("mock_wiim_controller")
async def test_setup_retries_when_url_has_no_hostname(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a Home Assistant URL without a hostname causes setup to retry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wiim.util.get_url",
        return_value="not-a-url",
    ):
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
