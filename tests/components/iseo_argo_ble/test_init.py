"""Test the ISEO Argo BLE integration setup and teardown."""

import time
from unittest.mock import MagicMock, patch

from iseo_argo_ble import IseoAuthError, IseoConnectionError, LockState
import pytest

from homeassistant.components.iseo_argo_ble.const import DOMAIN, STATE_POLL_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_ADDRESS, setup_integration, trigger_poll

from tests.common import MockConfigEntry


def _device(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry
) -> dr.AnyDeviceEntry:
    """Return the device entry created for the lock."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.unique_id), entry.entry_id
    )
    assert device is not None
    return device


async def test_setup_and_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a config entry is set up and unloaded cleanly."""
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_iseo_client")
async def test_setup_retries_when_device_not_found(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried while the lock is not advertising."""
    mock_config_entry.add_to_hass(hass)

    # Do not inject an advertisement: the lock is not in the Bluetooth cache.
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_firmware_version_stored_on_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test the firmware version reported by the lock reaches the device entry."""
    assert _device(device_registry, config_entry).sw_version == "1.2.3"


@pytest.mark.parametrize(
    "firmware_info",
    [None, "", "1.2.3"],
    ids=["missing", "empty", "unprefixed"],
)
@pytest.mark.usefixtures("mock_iseo_client")
async def test_firmware_version_variants(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    lock_state: LockState,
    firmware_info: str | None,
) -> None:
    """Test firmware versions the lock reports without the usual "FW:" prefix."""
    lock_state.firmware_info = firmware_info

    await setup_integration(hass, mock_config_entry)

    assert _device(device_registry, mock_config_entry).sw_version == (
        firmware_info or None
    )


async def test_poll_connection_error_logs_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing poll logs unavailable once, and back online on recovery."""
    mock_iseo_client.read_state.side_effect = IseoConnectionError("gone")

    await trigger_poll(hass)
    assert caplog.text.count("is unavailable") == 1

    caplog.clear()
    await trigger_poll(hass)
    assert "is unavailable" not in caplog.text

    caplog.clear()
    mock_iseo_client.read_state.side_effect = None
    await trigger_poll(hass)
    assert "is back online" in caplog.text


async def test_poll_unexpected_error_is_logged(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected error during a poll is logged with a traceback."""
    mock_iseo_client.read_state.side_effect = Exception("BOOM")

    await trigger_poll(hass)

    assert "unexpected error while polling" in caplog.text


async def test_poll_auth_error_logs_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a rejected identity is reported once, not on every poll."""
    mock_iseo_client.read_state.side_effect = IseoAuthError("rejected")

    await trigger_poll(hass)
    assert caplog.text.count("rejected the Home Assistant identity") == 1

    caplog.clear()
    await trigger_poll(hass)
    assert "rejected the Home Assistant identity" not in caplog.text


async def test_poll_is_throttled_to_the_poll_interval(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test an advertisement inside the poll interval does not read the lock."""
    interval = STATE_POLL_INTERVAL.total_seconds()
    # Date the reading below from the real clock, so the advertisements that
    # follow are measured against it rather than against the pinned one.
    with patch(
        "homeassistant.components.iseo_argo_ble.coordinator.monotonic_time_coarse",
        side_effect=time.monotonic,
    ):
        await trigger_poll(hass)
    mock_iseo_client.read_state.reset_mock()

    await trigger_poll(hass, after=interval - 1)
    mock_iseo_client.read_state.assert_not_called()

    await trigger_poll(hass, after=interval + 1)
    mock_iseo_client.read_state.assert_called_once()


async def test_no_poll_without_door_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    lock_state: LockState,
) -> None:
    """Test locks without a door sensor are not connected to again."""
    lock_state.door_closed = None

    await setup_integration(hass, mock_config_entry)
    assert mock_iseo_client.read_state.call_count == 1

    await trigger_poll(hass)
    assert mock_iseo_client.read_state.call_count == 1


async def test_ble_device_refreshed_on_advertisement(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test each advertisement refreshes the client's Bluetooth device."""
    mock_iseo_client.update_ble_device.reset_mock()

    await trigger_poll(hass)

    assert mock_iseo_client.update_ble_device.call_args[0][0].address == MOCK_ADDRESS
