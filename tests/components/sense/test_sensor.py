"""The tests for Sense sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sense.const import ACTIVE_UPDATE_RATE, CONSUMPTION_ID
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import setup_platform
from .const import DEVICE_1_NAME, DEVICE_1_POWER, DEVICE_2_NAME, DEVICE_2_POWER

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
    await setup_platform(hass, config_entry, SENSOR_DOMAIN)

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == STATE_UNAVAILABLE

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == "0"

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == "0"

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == f"{DEVICE_1_POWER:.0f}"

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == "0"

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == f"{DEVICE_1_POWER:.0f}"

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == f"{DEVICE_2_POWER:.0f}"


async def test_voltage_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense voltage sensors."""

    type(mock_sense).active_voltage = PropertyMock(return_value=[0, 0])

    await setup_platform(hass, config_entry, SENSOR_DOMAIN)

    state = hass.states.get("sensor.l1_voltage")
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.l2_voltage")
    assert state.state == STATE_UNAVAILABLE

    type(mock_sense).active_voltage = PropertyMock(return_value=[120, 121])
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.l1_voltage")
    assert state.state == "120"

    state = hass.states.get("sensor.l2_voltage")
    assert state.state == "121"

    type(mock_sense).active_voltage = PropertyMock(return_value=[122, 123])
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.l1_voltage")
    assert state.state == "122"

    state = hass.states.get("sensor.l2_voltage")
    assert state.state == "123"


async def test_active_power_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense power sensors."""

    await setup_platform(hass, config_entry, SENSOR_DOMAIN)

    state = hass.states.get("sensor.energy_usage")
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.energy_production")
    assert state.state == STATE_UNAVAILABLE

    type(mock_sense).active_power = PropertyMock(return_value=400)
    type(mock_sense).active_solar_power = PropertyMock(return_value=500)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_usage")
    assert state.state == "400"

    state = hass.states.get("sensor.energy_production")
    assert state.state == "500"

    type(mock_sense).active_power = PropertyMock(return_value=600)
    type(mock_sense).active_solar_power = PropertyMock(return_value=700)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_usage")
    assert state.state == "600"

    state = hass.states.get("sensor.energy_production")
    assert state.state == "700"


async def test_trend_energy_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense power sensors."""
    mock_sense.get_trend.side_effect = lambda sensor_type, variant: {
        ("DAY", "usage"): 100,
        ("DAY", "production"): 200,
        ("DAY", "from_grid"): 300,
        ("DAY", "to_grid"): 400,
        ("DAY", "net_production"): 500,
        ("DAY", "production_pct"): 600,
        ("DAY", "solar_powered"): 700,
    }.get((sensor_type, variant), 0)

    await setup_platform(hass, config_entry, SENSOR_DOMAIN)

    state = hass.states.get("sensor.daily_usage")
    assert state.state == "100"

    state = hass.states.get("sensor.daily_production")
    assert state.state == "200"

    state = hass.states.get("sensor.daily_from_grid")
    assert state.state == "300"

    state = hass.states.get("sensor.daily_to_grid")
    assert state.state == "400"

    state = hass.states.get("sensor.daily_net_production")
    assert state.state == "500"

    mock_sense.get_trend.side_effect = lambda sensor_type, variant: {
        ("DAY", "usage"): 1000,
        ("DAY", "production"): 2000,
        ("DAY", "from_grid"): 3000,
        ("DAY", "to_grid"): 4000,
        ("DAY", "net_production"): 5000,
        ("DAY", "production_pct"): 6000,
        ("DAY", "solar_powered"): 7000,
    }.get((sensor_type, variant), 0)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=600))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.daily_usage")
    assert state.state == "1000"

    state = hass.states.get("sensor.daily_production")
    assert state.state == "2000"

    state = hass.states.get("sensor.daily_from_grid")
    assert state.state == "3000"

    state = hass.states.get("sensor.daily_to_grid")
    assert state.state == "4000"

    state = hass.states.get("sensor.daily_net_production")
    assert state.state == "5000"
