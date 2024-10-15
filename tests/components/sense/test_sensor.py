"""The tests for Sense sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock

from homeassistant.components.sense.const import (
    ACTIVE_UPDATE_RATE,
    CONSUMPTION_ID,
    CONSUMPTION_NAME,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import (
    DEVICE_1_ICON,
    DEVICE_1_ID,
    DEVICE_1_NAME,
    DEVICE_1_POWER,
    DEVICE_2_ICON,
    DEVICE_2_ID,
    DEVICE_2_NAME,
    DEVICE_2_POWER,
    MONITOR_ID,
    setup_platform,
)

from tests.common import async_fire_time_changed


async def test_device_power_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_sense: MagicMock
) -> None:
    """Test the Sense device power sensors."""
    await setup_platform(hass, SENSOR_DOMAIN)

    entity = entity_registry.async_get(
        f"sensor.{DEVICE_1_NAME.lower()}_{CONSUMPTION_ID}"
    )
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-{DEVICE_1_ID}-{CONSUMPTION_ID}"

    entity = entity_registry.async_get(
        f"sensor.{DEVICE_2_NAME.lower()}_{CONSUMPTION_ID}"
    )
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-{DEVICE_2_ID}-{CONSUMPTION_ID}"

    state = hass.states.get(f"sensor.{DEVICE_1_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ICON) == f"mdi:{DEVICE_1_ICON}"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{DEVICE_1_NAME} {CONSUMPTION_NAME}"
    )

    state = hass.states.get(f"sensor.{DEVICE_2_NAME.lower()}_{CONSUMPTION_ID}")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ICON) == f"mdi:{DEVICE_2_ICON}"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == f"{DEVICE_2_NAME} {CONSUMPTION_NAME}"
    )

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
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_sense: MagicMock
) -> None:
    """Test the Sense voltage sensors."""

    type(mock_sense).active_voltage = PropertyMock(return_value=[0, 0])

    await setup_platform(hass, SENSOR_DOMAIN)

    entity = entity_registry.async_get("sensor.l1_voltage")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-L1"

    entity = entity_registry.async_get("sensor.l2_voltage")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-L2"

    state = hass.states.get("sensor.l1_voltage")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "L1 Voltage"

    state = hass.states.get("sensor.l2_voltage")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "L2 Voltage"

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
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_sense: MagicMock
) -> None:
    """Test the Sense power sensors."""

    type(mock_sense).active_power = PropertyMock(return_value=0)

    await setup_platform(hass, SENSOR_DOMAIN)

    entity = entity_registry.async_get("sensor.energy_usage")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-active-usage"

    entity = entity_registry.async_get("sensor.energy_production")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-active-production"

    state = hass.states.get("sensor.energy_usage")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy Usage"

    state = hass.states.get("sensor.energy_production")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Energy Production"

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

    state = hass.states.get("sensor.energy_usage")
    assert state.state == "600"

    state = hass.states.get("sensor.energy_production")
    assert state.state == "700"


async def test_trend_energy_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_sense: MagicMock
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

    await setup_platform(hass, SENSOR_DOMAIN)

    entity = entity_registry.async_get("sensor.daily_usage")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-daily-usage"

    entity = entity_registry.async_get("sensor.daily_production")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-daily-production"

    entity = entity_registry.async_get("sensor.daily_from_grid")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-daily-from_grid"

    entity = entity_registry.async_get("sensor.daily_to_grid")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-daily-to_grid"

    entity = entity_registry.async_get("sensor.daily_net_production")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-daily-net_production"

    entity = entity_registry.async_get("sensor.daily_net_production_percentage")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-daily-production_pct"

    entity = entity_registry.async_get("sensor.daily_solar_powered_percentage")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-daily-solar_powered"

    state = hass.states.get("sensor.daily_usage")
    state = hass.states.get("sensor.daily_usage")
    assert state.state == "100"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Daily Usage"

    state = hass.states.get("sensor.daily_production")
    assert state.state == "200"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Daily Production"

    state = hass.states.get("sensor.daily_from_grid")
    assert state.state == "300"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Daily From Grid"

    state = hass.states.get("sensor.daily_to_grid")
    assert state.state == "400"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Daily To Grid"

    state = hass.states.get("sensor.daily_net_production")
    assert state.state == "500"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Daily Net Production"
