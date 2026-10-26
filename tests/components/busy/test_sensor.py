"""Test shared polling sensors."""

from unittest.mock import AsyncMock

from busylib import types
from busylib.exceptions import BusyBarRequestError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
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
    assert snapshot == {
        state.entity_id: (state.state, state.attributes.get("unit_of_measurement"))
        for state in hass.states.async_all("sensor")
    }
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    assert len(entries) == 3
    device = device_registry.async_get_device_by_identifier(
        ("busy", init_integration.unique_id), init_integration.entry_id
    )
    assert device is not None
    assert (device.manufacturer, device.model, device.serial_number) == (
        "BUSY",
        "BUSY Bar",
        "BUSY123",
    )
    assert device.sw_version == "1.0"
    assert device.hw_version == "BB.1"
    assert device.configuration_url == "http://192.168.50.20"


async def test_poll_failure_and_recovery(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Share two requests per poll and recover without reloading."""
    mock_client.wifi_status.side_effect = BusyBarRequestError("offline")
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.busy_bar_battery").state == "unavailable"
    assert "Error fetching BUSY Bar data" in caplog.text
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
