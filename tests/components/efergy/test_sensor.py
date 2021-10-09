"""The tests for Efergy sensor platform."""

from homeassistant.components.efergy.sensor import SENSOR_TYPES
from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.setup import async_setup_component

from . import MULTI_SENSOR_TOKEN, setup_platform

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensor_readings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test for successfully setting up the Efergy platform."""
    for description in SENSOR_TYPES:
        description.entity_registry_enabled_default = True
    entry = await setup_platform(hass, aioclient_mock, SENSOR_DOMAIN)
    ent_reg: EntityRegistry = er.async_get(hass)

    state = hass.states.get("sensor.power_usage")
    assert state.state == "1580"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    state = hass.states.get("sensor.energy_budget")
    assert state.state == "ok"
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    state = hass.states.get("sensor.daily_consumption")
    assert state.state == "38.21"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    state = hass.states.get("sensor.weekly_consumption")
    assert state.state == "267.47"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    state = hass.states.get("sensor.monthly_consumption")
    assert state.state == "1069.88"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    state = hass.states.get("sensor.yearly_consumption")
    assert state.state == "13373.50"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    state = hass.states.get("sensor.daily_energy_cost")
    assert state.state == "5.27"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "EUR"
    state = hass.states.get("sensor.weekly_energy_cost")
    assert state.state == "36.89"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "EUR"
    state = hass.states.get("sensor.monthly_energy_cost")
    assert state.state == "147.56"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "EUR"
    state = hass.states.get("sensor.yearly_energy_cost")
    assert state.state == "1844.50"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_MONETARY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "EUR"
    entity = ent_reg.async_get("sensor.power_usage_728386")
    assert entity.disabled_by == er.DISABLED_INTEGRATION
    ent_reg.async_update_entity(entity.entity_id, **{"disabled_by": None})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.power_usage_728386")
    assert state.state == "1628"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT


async def test_multi_sensor_readings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test for multiple sensors in one household."""
    for description in SENSOR_TYPES:
        description.entity_registry_enabled_default = True
    await async_setup_component(hass, HA_DOMAIN, {})
    await setup_platform(hass, aioclient_mock, SENSOR_DOMAIN, MULTI_SENSOR_TOKEN)
    state = hass.states.get("sensor.power_usage_728386")
    assert state.state == "218"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    state = hass.states.get("sensor.power_usage_0")
    assert state.state == "1808"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    state = hass.states.get("sensor.power_usage_728387")
    assert state.state == "312"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
