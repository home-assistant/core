"""Test the Energy sensors."""
from homeassistant.components.energy import data
from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_MONETARY,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def setup_integration(hass):
    """Set up the integration."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    await hass.async_block_till_done()


async def test_cost_sensor_no_states(hass, hass_storage) -> None:
    """Test sensors are created."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["home_consumption"].append(
        {
            "stat_consumption": "foo",
            "entity_consumption": "foo",
            "stat_cost": None,
            "entity_energy_price": "bar",
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }
    await setup_integration(hass)
    # TODO: No states, should the cost entity refuse to setup?


async def test_cost_sensor(hass, hass_storage) -> None:
    """Test sensors are created."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["home_consumption"].append(
        {
            "stat_consumption": "sensor.energy_consumption",
            "entity_consumption": "sensor.energy_consumption",
            "stat_cost": None,
            "entity_energy_price": "sensor.energy_price",
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    last_reset = dt_util.utc_from_timestamp(0).isoformat()
    hass.states.async_set("sensor.energy_consumption", "0", {"last_reset": last_reset})
    hass.states.async_set("sensor.energy_price", "1")

    await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_MONETARY
    assert state.attributes[ATTR_LAST_RESET] == last_reset
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€"

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.energy_consumption_cost")
    assert entry.unique_id == "energy_energy_consumption cost"

    hass.states.async_set("sensor.energy_consumption", "10", {"last_reset": last_reset})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "10.0"

    hass.states.async_set("sensor.energy_price", "2", {"last_reset": last_reset})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "20.0"
