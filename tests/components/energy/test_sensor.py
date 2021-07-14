"""Test the Energy sensors."""
from datetime import timedelta
from unittest.mock import patch

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

# from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def setup_integration(hass):
    """Set up the integration."""
    assert await async_setup_component(
        hass, "energy", {"recorder": {"db_url": "sqlite://"}}
    )
    await hass.async_block_till_done()


async def test_cost_sensor_no_states(hass, hass_storage) -> None:
    """Test sensors are created."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "foo",
                    "entity_energy_from": "foo",
                    "stat_cost": None,
                    "entity_energy_price": "bar",
                    "number_energy_price": None,
                }
            ],
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }
    await setup_integration(hass)
    # TODO: No states, should the cost entity refuse to setup?


async def test_cost_sensor_price_entity(hass, hass_storage) -> None:
    """Test sensors are created."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
                    "entity_energy_from": "sensor.energy_consumption",
                    "stat_cost": None,
                    "entity_energy_price": "sensor.energy_price",
                    "number_energy_price": None,
                }
            ],
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    last_reset = dt_util.utc_from_timestamp(0).isoformat()
    hass.states.async_set(
        "sensor.energy_consumption",
        "0",
        {"last_reset": last_reset},
    )
    hass.states.async_set("sensor.energy_price", "1")

    now = dt_util.utcnow()

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_MONETARY
    assert state.attributes[ATTR_LAST_RESET] == now.isoformat()
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€"

    # # Unique ID temp disabled
    # # entity_registry = er.async_get(hass)
    # # entry = entity_registry.async_get("sensor.energy_consumption_cost")
    # # assert entry.unique_id == "energy_energy_consumption cost"

    hass.states.async_set("sensor.energy_consumption", "10", {"last_reset": last_reset})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "10.0"

    # Nothing happens when price changes
    hass.states.async_set("sensor.energy_price", "2")
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "10.0"

    hass.states.async_set(
        "sensor.energy_consumption", "14.5", {"last_reset": last_reset}
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "19.0"

    hass.states.async_set(
        "sensor.energy_consumption",
        "4",
        {"last_reset": (now + timedelta(seconds=1)).isoformat()},
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "27.0"


async def test_cost_sensor_fixed_price(hass, hass_storage, hass_ws_client) -> None:
    """Test sensors are created."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
                    "entity_energy_from": "sensor.energy_consumption",
                    "stat_cost": None,
                    "entity_energy_price": None,
                    "number_energy_price": 1,
                }
            ],
            "flow_to": [],
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "unknown"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_MONETARY
    assert ATTR_LAST_RESET not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€"

    now = dt_util.utcnow()
    last_reset = dt_util.utc_from_timestamp(0).isoformat()

    # Test setting up dependent entities later.
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            "sensor.energy_consumption",
            "0",
            {"last_reset": last_reset},
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_MONETARY
    assert state.attributes[ATTR_LAST_RESET] == now.isoformat()
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€"

    hass.states.async_set("sensor.energy_consumption", "10", {"last_reset": last_reset})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "10.0"

    # Update price
    energy_data["energy_sources"][0]["flow_from"] = [
        {
            "stat_energy_from": "sensor.energy_consumption",
            "entity_energy_from": "sensor.energy_consumption",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 2,
        }
    ]
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "energy/save_prefs", **energy_data})
    msg = await client.receive_json()
    assert msg["success"]

    hass.states.async_set(
        "sensor.energy_consumption", "14.5", {"last_reset": last_reset}
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "19.0"
