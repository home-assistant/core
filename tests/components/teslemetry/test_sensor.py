"""Test the Teslemetry sensor platform."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

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
) -> None:
    """Tests that the sensor entities with the legacy polling are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    # Force the vehicle to use polling
    with patch("tesla_fleet_api.teslemetry.Vehicle.pre2021", return_value=True):
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
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the sensor entities with streaming are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    entry = await setup_platform(hass, [Platform.SENSOR])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.DETAILED_CHARGE_STATE: "DetailedChargeStateCharging",
                Signal.BATTERY_LEVEL: 90,
                Signal.AC_CHARGING_ENERGY_IN: 10,
                Signal.AC_CHARGING_POWER: 2,
                Signal.CHARGING_CABLE_TYPE: None,
                Signal.TIME_TO_FULL_CHARGE: 0.166666667,
                Signal.MINUTES_TO_ARRIVAL: None,
            },
            "credits": {
                "type": "wake_up",
                "cost": 20,
                "name": "wake_up",
                "balance": 1980,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Assert the entities restored their values
    for entity_id in (
        "sensor.test_charging",
        "sensor.test_battery_level",
        "sensor.test_charge_energy_added",
        "sensor.test_charger_power",
        "sensor.test_charge_cable",
        "sensor.test_time_to_full_charge",
        "sensor.test_time_to_arrival",
        "sensor.teslemetry_credits",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-state")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tariff_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,  # Keep this if other parts of setup_platform need it
    mock_site_info,  # Add fixture for energy site info
    mock_live_status,  # Add fixture for energy site status
) -> None:
    """Tests that the tariff sensor entities are correct."""

    TZ = dt_util.get_default_time_zone()
    # Set time to a point where a known tariff period is active based on site_info.json
    # Example: Summer, Off Peak (10:00 falls between 21:00 and 16:00 next day, crossing midnight)
    freezer.move_to(datetime(2024, 1, 1, 10, 0, 0, tzinfo=TZ))

    # Ensure Platform.SENSOR is used for setup
    entry = await setup_platform(hass, [Platform.SENSOR])

    # Assert specific tariff sensor entities
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)
