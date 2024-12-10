"""Test the Teslemetry sensor platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal
from teslemetry_stream.stream import recursive_match

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.components.teslemetry.models import TeslemetryData
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_listen: AsyncMock,
) -> None:
    """Tests that the sensor entities with the legacy polling are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    # Force the vehicle to use polling
    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.pre2021", return_value=True
    ):
        entry = await setup_platform(hass, [Platform.SENSOR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    # Coordinator refresh
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_listen: AsyncMock,
) -> None:
    """Tests that the sensor entities with streaming are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    entry = await setup_platform(hass, [Platform.SENSOR])

    # Stream update
    runtime_data: TeslemetryData = entry.runtime_data
    event = {
        "vin": VEHICLE_DATA_ALT["response"]["vin"],
        "data": {
            Signal.DETAILED_CHARGE_STATE: "DetailedChargeStateCharging",
            Signal.BATTERY_LEVEL: 90,
            Signal.AC_CHARGING_ENERGY_IN: 10,
            Signal.AC_CHARGING_POWER: 2,
            Signal.CHARGING_CABLE_TYPE: None,
            Signal.TIME_TO_FULL_CHARGE: 10,
            Signal.MINUTES_TO_ARRIVAL: None,
        },
        "createdAt": "2024-10-04T10:45:17.537Z",
    }
    for listener, filters in runtime_data.vehicles[0].stream._listeners.values():
        if recursive_match(filters, event):
            listener(event)
    await hass.async_block_till_done()

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Assert the entities restored their values
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)
