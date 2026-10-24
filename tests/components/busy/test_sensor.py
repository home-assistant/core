"""Test shared polling sensors."""

from unittest.mock import AsyncMock

from busylib import types
from busylib.exceptions import BusyBarRequestError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the three readings and their shared device metadata."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)
    device = device_registry.async_get_device_by_identifier(
        ("busy", init_integration.unique_id), init_integration.entry_id
    )
    assert device is not None
    assert (device.manufacturer, device.model, device.serial_number) == (
        "BUSY",
        "BUSY Bar",
        "BUSY123",
    )
    assert device.sw_version == "1.0 (release)"


async def test_poll_failure_and_recovery(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Share two requests per poll and recover without reloading."""
    mock_client.wifi_status.side_effect = BusyBarRequestError("offline")
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.busy_bar_battery").state == "unavailable"
    mock_client.wifi_status.side_effect = None
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.busy_bar_battery").state == "82"
    assert mock_client.status.await_count == mock_client.wifi_status.await_count == 3


@pytest.mark.parametrize(
    "firmware", [None, types.StatusFirmware(version="1.0"), types.StatusFirmware()]
)
async def test_missing_readings(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    firmware: types.StatusFirmware | None,
) -> None:
    """Handle optional metadata and a disconnected Wi-Fi network."""
    mock_client.status.return_value = types.Status(firmware=firmware)
    mock_client.wifi_status.return_value = types.StatusResponse(
        state=types.WifiState.DISCONNECTED
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.busy_bar_battery").state == "unknown"
    assert hass.states.get("sensor.busy_bar_wi_fi_signal").state == "unknown"
    assert hass.states.get("sensor.busy_bar_wi_fi_network").state == "unknown"
