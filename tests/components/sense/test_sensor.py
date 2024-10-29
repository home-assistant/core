"""The tests for Sense sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from sense_energy import Scale
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sense.const import ACTIVE_UPDATE_RATE, TREND_UPDATE_RATE
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import setup_platform
from .const import (
    DEVICE_1_DAY_ENERGY,
    DEVICE_1_NAME,
    DEVICE_2_DAY_ENERGY,
    DEVICE_2_NAME,
    DEVICE_2_POWER,
    MONITOR_ID,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Sensor."""
    await setup_platform(hass, config_entry, Platform.SENSOR)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_device_power_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense device power sensors."""
    device_1, device_2 = mock_sense.devices
    device_1.power_w = 0
    device_2.power_w = 0
    await setup_platform(hass, config_entry, SENSOR_DOMAIN)
    device_1, device_2 = mock_sense.devices

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_power")
    assert state.state == "0"

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_power")
    assert state.state == "0"

    device_2.power_w = DEVICE_2_POWER
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_power")
    assert state.state == "0"

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_power")
    assert state.state == f"{DEVICE_2_POWER:.1f}"


async def test_device_energy_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sense device power sensors."""
    await setup_platform(hass, config_entry, SENSOR_DOMAIN)
    device_1, device_2 = mock_sense.devices

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_daily_energy")
    assert state.state == f"{DEVICE_1_DAY_ENERGY:.0f}"

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_daily_energy")
    assert state.state == f"{DEVICE_2_DAY_ENERGY:.0f}"

    device_1.energy_kwh[Scale.DAY] = 0
    device_2.energy_kwh[Scale.DAY] = 0
    freezer.tick(timedelta(seconds=TREND_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_daily_energy")
    assert state.state == "0"

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_daily_energy")
    assert state.state == "0"

    device_2.energy_kwh[Scale.DAY] = DEVICE_1_DAY_ENERGY
    freezer.tick(timedelta(seconds=TREND_UPDATE_RATE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_daily_energy")
    assert state.state == "0"

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_daily_energy")
    assert state.state == f"{DEVICE_1_DAY_ENERGY:.0f}"


async def test_voltage_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense voltage sensors."""

    type(mock_sense).active_voltage = PropertyMock(return_value=[120, 121])

    await setup_platform(hass, config_entry, SENSOR_DOMAIN)

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_l1_voltage")
    assert state.state == "120"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_l2_voltage")
    assert state.state == "121"

    type(mock_sense).active_voltage = PropertyMock(return_value=[122, 123])
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_l1_voltage")
    assert state.state == "122"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_l2_voltage")
    assert state.state == "123"


async def test_active_power_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense power sensors."""

    type(mock_sense).active_power = PropertyMock(return_value=400)
    type(mock_sense).active_solar_power = PropertyMock(return_value=500)

    await setup_platform(hass, config_entry, SENSOR_DOMAIN)

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state.state == "400"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_production")
    assert state.state == "500"

    type(mock_sense).active_power = PropertyMock(return_value=600)
    type(mock_sense).active_solar_power = PropertyMock(return_value=700)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_energy")
    assert state.state == "600"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_production")
    assert state.state == "700"


async def test_trend_energy_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense power sensors."""
    mock_sense.get_stat.side_effect = lambda sensor_type, variant: {
        (Scale.DAY, "usage"): 100,
        (Scale.DAY, "production"): 200,
        (Scale.DAY, "from_grid"): 300,
        (Scale.DAY, "to_grid"): 400,
        (Scale.DAY, "net_production"): 500,
        (Scale.DAY, "production_pct"): 600,
        (Scale.DAY, "solar_powered"): 700,
    }.get((sensor_type, variant), 0)

    await setup_platform(hass, config_entry, SENSOR_DOMAIN)

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_energy")
    assert state.state == "100"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_production")
    assert state.state == "200"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_from_grid")
    assert state.state == "300"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_to_grid")
    assert state.state == "400"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_net_production")
    assert state.state == "500"

    mock_sense.get_stat.side_effect = lambda sensor_type, variant: {
        (Scale.DAY, "usage"): 1000,
        (Scale.DAY, "production"): 2000,
        (Scale.DAY, "from_grid"): 3000,
        (Scale.DAY, "to_grid"): 4000,
        (Scale.DAY, "net_production"): 5000,
        (Scale.DAY, "production_pct"): 6000,
        (Scale.DAY, "solar_powered"): 7000,
    }.get((sensor_type, variant), 0)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=600))
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_energy")
    assert state.state == "1000"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_production")
    assert state.state == "2000"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_from_grid")
    assert state.state == "3000"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_to_grid")
    assert state.state == "4000"

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_net_production")
    assert state.state == "5000"
