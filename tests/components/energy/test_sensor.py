"""Test the Energy sensors."""
import copy
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.energy import data
from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
)
from homeassistant.components.sensor.recorder import compile_statistics
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_MONETARY,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_init_recorder_component
from tests.components.recorder.common import async_wait_recording_done_without_instance


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


@pytest.mark.parametrize("initial_energy,initial_cost", [(0, "0.0"), (None, "unknown")])
@pytest.mark.parametrize(
    "price_entity,fixed_price", [("sensor.energy_price", None), (None, 1)]
)
async def test_cost_sensor_price_entity(
    hass,
    hass_storage,
    hass_ws_client,
    initial_energy,
    initial_cost,
    price_entity,
    fixed_price,
) -> None:
    """Test energy cost price from sensor entity."""

    def _compile_statistics(_):
        return compile_statistics(hass, now, now + timedelta(seconds=1))

    await async_init_recorder_component(hass)
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
                    "entity_energy_from": "sensor.energy_consumption",
                    "stat_cost": None,
                    "entity_energy_price": price_entity,
                    "number_energy_price": fixed_price,
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

    now = dt_util.utcnow()
    last_reset = dt_util.utc_from_timestamp(0).isoformat()

    # Optionally initialize dependent entities
    if initial_energy is not None:
        hass.states.async_set(
            "sensor.energy_consumption", initial_energy, {"last_reset": last_reset}
        )
    hass.states.async_set("sensor.energy_price", "1")

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == initial_cost
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_MONETARY
    if initial_cost != "unknown":
        assert state.attributes[ATTR_LAST_RESET] == now.isoformat()
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€"

    # Optional late setup of dependent entities
    if initial_energy is None:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(
                "sensor.energy_consumption", "0", {"last_reset": last_reset}
            )
            await hass.async_block_till_done()

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

    # Energy use bumped to 10 kWh
    hass.states.async_set("sensor.energy_consumption", "10", {"last_reset": last_reset})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "10.0"  # 0 € + (10-0) kWh * 1 €/kWh = 10 €

    # Nothing happens when price changes
    if price_entity is not None:
        hass.states.async_set(price_entity, "2")
        await hass.async_block_till_done()
    else:
        energy_data = copy.deepcopy(energy_data)
        energy_data["energy_sources"][0]["flow_from"][0]["number_energy_price"] = 2
        client = await hass_ws_client(hass)
        await client.send_json({"id": 5, "type": "energy/save_prefs", **energy_data})
        msg = await client.receive_json()
        assert msg["success"]
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "10.0"  # 10 € + (10-10) kWh * 2 €/kWh = 10 €

    # Additional consumption is using the new price
    hass.states.async_set(
        "sensor.energy_consumption", "14.5", {"last_reset": last_reset}
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "19.0"  # 10 € + (14.5-10) kWh * 2 €/kWh = 19 €

    # Check generated statistics
    await async_wait_recording_done_without_instance(hass)
    statistics = await hass.loop.run_in_executor(None, _compile_statistics, hass)
    assert "sensor.energy_consumption_cost" in statistics
    assert statistics["sensor.energy_consumption_cost"]["stat"]["sum"] == 19.0

    # Energy sensor is reset, with start point at 4kWh
    last_reset = (now + timedelta(seconds=1)).isoformat()
    hass.states.async_set("sensor.energy_consumption", "4", {"last_reset": last_reset})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"  # 0 € + (4-4) kWh * 2 €/kWh = 0 €

    # Energy use bumped to 10 kWh
    hass.states.async_set("sensor.energy_consumption", "10", {"last_reset": last_reset})
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "12.0"  # 0 € + (10-4) kWh * 2 €/kWh = 12 €

    # Check generated statistics
    await async_wait_recording_done_without_instance(hass)
    statistics = await hass.loop.run_in_executor(None, _compile_statistics, hass)
    assert "sensor.energy_consumption_cost" in statistics
    assert statistics["sensor.energy_consumption_cost"]["stat"]["sum"] == 31.0
