"""Test the Powerfox init module."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from powerfox import (
    PowerfoxAuthenticationError,
    PowerfoxConnectionError,
    PowerfoxNoDataError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.powerfox.const import DEVICE_LIST_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

WATER_METER_ID = "9x9x1f12xx4x"
GAS_METER_ID = "9x9x1f12xx6x"


def _get_device(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry, device_id: str
) -> dr.DeviceEntry | None:
    """Return the registered device for a Powerfox device id."""
    return device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), entry.entry_id
    )


async def _async_poll_device_list(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance time so the device list is fetched again."""
    freezer.tick(DEVICE_LIST_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("exception", [PowerfoxConnectionError, PowerfoxNoDataError])
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
) -> None:
    """Test the Powerfox configuration entry not ready."""
    mock_powerfox_client.all_devices.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("method", ["all_devices", "device"])
async def test_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method: str,
) -> None:
    """Test ConfigEntryAuthFailed when authentication fails."""
    getattr(mock_powerfox_client, method).side_effect = PowerfoxAuthenticationError
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_new_device_is_added(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device added to the account is set up without user interaction."""
    all_devices = mock_powerfox_client.all_devices.return_value
    mock_powerfox_client.all_devices.return_value = [
        device for device in all_devices if device.id != GAS_METER_ID
    ]
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    assert not _get_device(device_registry, mock_config_entry, GAS_METER_ID)

    mock_powerfox_client.all_devices.return_value = all_devices
    await _async_poll_device_list(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert _get_device(device_registry, mock_config_entry, GAS_METER_ID)
    assert hass.states.get("sensor.gasopti_gas_consumption_today")


async def test_stale_device_is_removed(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device removed from the account is removed from Home Assistant."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    assert _get_device(device_registry, mock_config_entry, WATER_METER_ID)
    assert hass.states.get("sensor.wateropti_cold_water")

    mock_powerfox_client.all_devices.return_value = [
        device
        for device in mock_powerfox_client.all_devices.return_value
        if device.id != WATER_METER_ID
    ]
    await _async_poll_device_list(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not _get_device(device_registry, mock_config_entry, WATER_METER_ID)
    assert not hass.states.get("sensor.wateropti_cold_water")


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(None, id="unchanged"),
        pytest.param(PowerfoxConnectionError, id="connection_error"),
        pytest.param(PowerfoxNoDataError, id="no_devices"),
    ],
)
async def test_devices_kept_without_device_list_change(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    side_effect: type[Exception] | None,
) -> None:
    """Test devices are kept and no reload happens without a known list change."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    mock_powerfox_client.all_devices.side_effect = side_effect
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_schedule_reload:
        await _async_poll_device_list(hass, freezer)

    assert mock_powerfox_client.all_devices.await_count == 2
    mock_schedule_reload.assert_not_called()
    assert _get_device(device_registry, mock_config_entry, WATER_METER_ID)


async def test_device_list_auth_failed_starts_reauth(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an authentication error while polling the device list starts reauth."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    mock_powerfox_client.all_devices.side_effect = PowerfoxAuthenticationError
    await _async_poll_device_list(hass, freezer)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
