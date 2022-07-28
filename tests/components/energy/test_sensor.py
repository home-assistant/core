"""Test the Energy sensors."""
import copy
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.energy import data
from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.sensor.recorder import compile_statistics
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    STATE_UNKNOWN,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.components.recorder.common import async_wait_recording_done


@pytest.fixture
async def setup_integration(recorder_mock):
    """Set up the integration."""

    async def setup_integration(hass):
        assert await async_setup_component(hass, "energy", {})
        await hass.async_block_till_done()

    return setup_integration


def get_statistics_for_entity(statistics_results, entity_id):
    """Get statistics for a certain entity, or None if there is none."""
    for statistics_result in statistics_results:
        if statistics_result["meta"]["statistic_id"] == entity_id:
            return statistics_result
    return None


async def test_cost_sensor_no_states(hass, hass_storage, setup_integration) -> None:
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


async def test_cost_sensor_attributes(hass, hass_storage, setup_integration) -> None:
    """Test sensor attributes."""
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

    registry = er.async_get(hass)
    cost_sensor_entity_id = "sensor.energy_consumption_cost"
    entry = registry.async_get(cost_sensor_entity_id)
    assert entry.entity_category is None
    assert entry.disabled_by is None
    assert entry.hidden_by == er.RegistryEntryHider.INTEGRATION


@pytest.mark.parametrize("initial_energy,initial_cost", [(0, "0.0"), (None, "unknown")])
@pytest.mark.parametrize(
    "price_entity,fixed_price", [("sensor.energy_price", None), (None, 1)]
)
@pytest.mark.parametrize(
    "usage_sensor_entity_id,cost_sensor_entity_id,flow_type",
    [
        ("sensor.energy_consumption", "sensor.energy_consumption_cost", "flow_from"),
        (
            "sensor.energy_production",
            "sensor.energy_production_compensation",
            "flow_to",
        ),
    ],
)
async def test_cost_sensor_price_entity_total_increasing(
    hass,
    hass_storage,
    hass_ws_client,
    setup_integration,
    initial_energy,
    initial_cost,
    price_entity,
    fixed_price,
    usage_sensor_entity_id,
    cost_sensor_entity_id,
    flow_type,
) -> None:
    """Test energy cost price from total_increasing type sensor entity."""

    def _compile_statistics(_):
        return compile_statistics(hass, now, now + timedelta(seconds=1)).platform_stats

    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }

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
            ]
            if flow_type == "flow_from"
            else [],
            "flow_to": [
                {
                    "stat_energy_to": "sensor.energy_production",
                    "entity_energy_to": "sensor.energy_production",
                    "stat_compensation": None,
                    "entity_energy_price": price_entity,
                    "number_energy_price": fixed_price,
                }
            ]
            if flow_type == "flow_to"
            else [],
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    now = dt_util.utcnow()
    last_reset_cost_sensor = now.isoformat()

    # Optionally initialize dependent entities
    if initial_energy is not None:
        hass.states.async_set(
            usage_sensor_entity_id,
            initial_energy,
            energy_attributes,
        )
    hass.states.async_set("sensor.energy_price", "1")

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == initial_cost
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    if initial_cost != "unknown":
        assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "EUR"

    # Optional late setup of dependent entities
    if initial_energy is None:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(
                usage_sensor_entity_id,
                "0",
                energy_attributes,
            )
            await hass.async_block_till_done()

    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "0.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "EUR"

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(cost_sensor_entity_id)
    assert entry
    postfix = "cost" if flow_type == "flow_from" else "compensation"
    assert entry.unique_id == f"{usage_sensor_entity_id}_grid_{postfix}"
    assert entry.hidden_by is er.RegistryEntryHider.INTEGRATION

    # Energy use bumped to 10 kWh
    hass.states.async_set(
        usage_sensor_entity_id,
        "10",
        energy_attributes,
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 0 EUR + (10-0) kWh * 1 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Nothing happens when price changes
    if price_entity is not None:
        hass.states.async_set(price_entity, "2")
        await hass.async_block_till_done()
    else:
        energy_data = copy.deepcopy(energy_data)
        energy_data["energy_sources"][0][flow_type][0]["number_energy_price"] = 2
        client = await hass_ws_client(hass)
        await client.send_json({"id": 5, "type": "energy/save_prefs", **energy_data})
        msg = await client.receive_json()
        assert msg["success"]
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 10 EUR + (10-10) kWh * 2 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Additional consumption is using the new price
    hass.states.async_set(
        usage_sensor_entity_id,
        "14.5",
        energy_attributes,
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "19.0"  # 10 EUR + (14.5-10) kWh * 2 EUR/kWh = 19 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Check generated statistics
    await async_wait_recording_done(hass)
    all_statistics = await hass.loop.run_in_executor(None, _compile_statistics, hass)
    statistics = get_statistics_for_entity(all_statistics, cost_sensor_entity_id)
    assert statistics["stat"]["sum"] == 19.0

    # Energy sensor has a small dip, no reset should be detected
    hass.states.async_set(
        usage_sensor_entity_id,
        "14",
        energy_attributes,
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "18.0"  # 19 EUR + (14-14.5) kWh * 2 EUR/kWh = 18 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Energy sensor is reset, with initial state at 4kWh, 0 kWh is used as zero-point
    hass.states.async_set(
        usage_sensor_entity_id,
        "4",
        energy_attributes,
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "8.0"  # 0 EUR + (4-0) kWh * 2 EUR/kWh = 8 EUR
    assert state.attributes[ATTR_LAST_RESET] != last_reset_cost_sensor
    last_reset_cost_sensor = state.attributes[ATTR_LAST_RESET]

    # Energy use bumped to 10 kWh
    hass.states.async_set(
        usage_sensor_entity_id,
        "10",
        energy_attributes,
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "20.0"  # 8 EUR + (10-4) kWh * 2 EUR/kWh = 20 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Check generated statistics
    await async_wait_recording_done(hass)
    all_statistics = await hass.loop.run_in_executor(None, _compile_statistics, hass)
    statistics = get_statistics_for_entity(all_statistics, cost_sensor_entity_id)
    assert statistics["stat"]["sum"] == 38.0


@pytest.mark.parametrize("initial_energy,initial_cost", [(0, "0.0"), (None, "unknown")])
@pytest.mark.parametrize(
    "price_entity,fixed_price", [("sensor.energy_price", None), (None, 1)]
)
@pytest.mark.parametrize(
    "usage_sensor_entity_id,cost_sensor_entity_id,flow_type",
    [
        ("sensor.energy_consumption", "sensor.energy_consumption_cost", "flow_from"),
        (
            "sensor.energy_production",
            "sensor.energy_production_compensation",
            "flow_to",
        ),
    ],
)
@pytest.mark.parametrize("energy_state_class", ["total", "measurement"])
async def test_cost_sensor_price_entity_total(
    hass,
    hass_storage,
    hass_ws_client,
    setup_integration,
    initial_energy,
    initial_cost,
    price_entity,
    fixed_price,
    usage_sensor_entity_id,
    cost_sensor_entity_id,
    flow_type,
    energy_state_class,
) -> None:
    """Test energy cost price from total type sensor entity."""

    def _compile_statistics(_):
        return compile_statistics(hass, now, now + timedelta(seconds=1)).platform_stats

    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: energy_state_class,
    }

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
            ]
            if flow_type == "flow_from"
            else [],
            "flow_to": [
                {
                    "stat_energy_to": "sensor.energy_production",
                    "entity_energy_to": "sensor.energy_production",
                    "stat_compensation": None,
                    "entity_energy_price": price_entity,
                    "number_energy_price": fixed_price,
                }
            ]
            if flow_type == "flow_to"
            else [],
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    now = dt_util.utcnow()
    last_reset = dt_util.utc_from_timestamp(0).isoformat()
    last_reset_cost_sensor = now.isoformat()

    # Optionally initialize dependent entities
    if initial_energy is not None:
        hass.states.async_set(
            usage_sensor_entity_id,
            initial_energy,
            {**energy_attributes, **{"last_reset": last_reset}},
        )
    hass.states.async_set("sensor.energy_price", "1")

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == initial_cost
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    if initial_cost != "unknown":
        assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "EUR"

    # Optional late setup of dependent entities
    if initial_energy is None:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(
                usage_sensor_entity_id,
                "0",
                {**energy_attributes, **{"last_reset": last_reset}},
            )
            await hass.async_block_till_done()

    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "0.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "EUR"

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(cost_sensor_entity_id)
    assert entry
    postfix = "cost" if flow_type == "flow_from" else "compensation"
    assert entry.unique_id == f"{usage_sensor_entity_id}_grid_{postfix}"
    assert entry.hidden_by is er.RegistryEntryHider.INTEGRATION

    # Energy use bumped to 10 kWh
    hass.states.async_set(
        usage_sensor_entity_id,
        "10",
        {**energy_attributes, **{"last_reset": last_reset}},
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 0 EUR + (10-0) kWh * 1 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Nothing happens when price changes
    if price_entity is not None:
        hass.states.async_set(price_entity, "2")
        await hass.async_block_till_done()
    else:
        energy_data = copy.deepcopy(energy_data)
        energy_data["energy_sources"][0][flow_type][0]["number_energy_price"] = 2
        client = await hass_ws_client(hass)
        await client.send_json({"id": 5, "type": "energy/save_prefs", **energy_data})
        msg = await client.receive_json()
        assert msg["success"]
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 10 EUR + (10-10) kWh * 2 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Additional consumption is using the new price
    hass.states.async_set(
        usage_sensor_entity_id,
        "14.5",
        {**energy_attributes, **{"last_reset": last_reset}},
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "19.0"  # 10 EUR + (14.5-10) kWh * 2 EUR/kWh = 19 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Check generated statistics
    await async_wait_recording_done(hass)
    all_statistics = await hass.loop.run_in_executor(None, _compile_statistics, hass)
    statistics = get_statistics_for_entity(all_statistics, cost_sensor_entity_id)
    assert statistics["stat"]["sum"] == 19.0

    # Energy sensor has a small dip
    hass.states.async_set(
        usage_sensor_entity_id,
        "14",
        {**energy_attributes, **{"last_reset": last_reset}},
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "18.0"  # 19 EUR + (14-14.5) kWh * 2 EUR/kWh = 18 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Energy sensor is reset, with initial state at 4kWh, 0 kWh is used as zero-point
    last_reset = (now + timedelta(seconds=1)).isoformat()
    hass.states.async_set(
        usage_sensor_entity_id,
        "4",
        {**energy_attributes, **{"last_reset": last_reset}},
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "8.0"  # 0 EUR + (4-0) kWh * 2 EUR/kWh = 8 EUR
    assert state.attributes[ATTR_LAST_RESET] != last_reset_cost_sensor
    last_reset_cost_sensor = state.attributes[ATTR_LAST_RESET]

    # Energy use bumped to 10 kWh
    hass.states.async_set(
        usage_sensor_entity_id,
        "10",
        {**energy_attributes, **{"last_reset": last_reset}},
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "20.0"  # 8 EUR + (10-4) kWh * 2 EUR/kWh = 20 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Check generated statistics
    await async_wait_recording_done(hass)
    all_statistics = await hass.loop.run_in_executor(None, _compile_statistics, hass)
    statistics = get_statistics_for_entity(all_statistics, cost_sensor_entity_id)
    assert statistics["stat"]["sum"] == 38.0


@pytest.mark.parametrize("initial_energy,initial_cost", [(0, "0.0"), (None, "unknown")])
@pytest.mark.parametrize(
    "price_entity,fixed_price", [("sensor.energy_price", None), (None, 1)]
)
@pytest.mark.parametrize(
    "usage_sensor_entity_id,cost_sensor_entity_id,flow_type",
    [
        ("sensor.energy_consumption", "sensor.energy_consumption_cost", "flow_from"),
        (
            "sensor.energy_production",
            "sensor.energy_production_compensation",
            "flow_to",
        ),
    ],
)
@pytest.mark.parametrize("energy_state_class", ["total"])
async def test_cost_sensor_price_entity_total_no_reset(
    hass,
    hass_storage,
    hass_ws_client,
    setup_integration,
    initial_energy,
    initial_cost,
    price_entity,
    fixed_price,
    usage_sensor_entity_id,
    cost_sensor_entity_id,
    flow_type,
    energy_state_class,
) -> None:
    """Test energy cost price from total type sensor entity with no last_reset."""

    def _compile_statistics(_):
        return compile_statistics(hass, now, now + timedelta(seconds=1)).platform_stats

    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: energy_state_class,
    }

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
            ]
            if flow_type == "flow_from"
            else [],
            "flow_to": [
                {
                    "stat_energy_to": "sensor.energy_production",
                    "entity_energy_to": "sensor.energy_production",
                    "stat_compensation": None,
                    "entity_energy_price": price_entity,
                    "number_energy_price": fixed_price,
                }
            ]
            if flow_type == "flow_to"
            else [],
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    now = dt_util.utcnow()
    last_reset_cost_sensor = now.isoformat()

    # Optionally initialize dependent entities
    if initial_energy is not None:
        hass.states.async_set(
            usage_sensor_entity_id,
            initial_energy,
            energy_attributes,
        )
    hass.states.async_set("sensor.energy_price", "1")

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == initial_cost
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    if initial_cost != "unknown":
        assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "EUR"

    # Optional late setup of dependent entities
    if initial_energy is None:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(
                usage_sensor_entity_id,
                "0",
                energy_attributes,
            )
            await hass.async_block_till_done()

    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "0.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "EUR"

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(cost_sensor_entity_id)
    assert entry
    postfix = "cost" if flow_type == "flow_from" else "compensation"
    assert entry.unique_id == f"{usage_sensor_entity_id}_grid_{postfix}"
    assert entry.hidden_by is er.RegistryEntryHider.INTEGRATION

    # Energy use bumped to 10 kWh
    hass.states.async_set(
        usage_sensor_entity_id,
        "10",
        energy_attributes,
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 0 EUR + (10-0) kWh * 1 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Nothing happens when price changes
    if price_entity is not None:
        hass.states.async_set(price_entity, "2")
        await hass.async_block_till_done()
    else:
        energy_data = copy.deepcopy(energy_data)
        energy_data["energy_sources"][0][flow_type][0]["number_energy_price"] = 2
        client = await hass_ws_client(hass)
        await client.send_json({"id": 5, "type": "energy/save_prefs", **energy_data})
        msg = await client.receive_json()
        assert msg["success"]
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 10 EUR + (10-10) kWh * 2 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Additional consumption is using the new price
    hass.states.async_set(
        usage_sensor_entity_id,
        "14.5",
        energy_attributes,
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "19.0"  # 10 EUR + (14.5-10) kWh * 2 EUR/kWh = 19 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Check generated statistics
    await async_wait_recording_done(hass)
    all_statistics = await hass.loop.run_in_executor(None, _compile_statistics, hass)
    statistics = get_statistics_for_entity(all_statistics, cost_sensor_entity_id)
    assert statistics["stat"]["sum"] == 19.0

    # Energy sensor has a small dip
    hass.states.async_set(
        usage_sensor_entity_id,
        "14",
        energy_attributes,
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "18.0"  # 19 EUR + (14-14.5) kWh * 2 EUR/kWh = 18 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Check generated statistics
    await async_wait_recording_done(hass)
    all_statistics = await hass.loop.run_in_executor(None, _compile_statistics, hass)
    statistics = get_statistics_for_entity(all_statistics, cost_sensor_entity_id)
    assert statistics["stat"]["sum"] == 18.0


@pytest.mark.parametrize(
    "energy_unit,factor",
    [
        (ENERGY_WATT_HOUR, 1000),
        (ENERGY_KILO_WATT_HOUR, 1),
        (ENERGY_MEGA_WATT_HOUR, 0.001),
    ],
)
async def test_cost_sensor_handle_energy_units(
    hass, hass_storage, setup_integration, energy_unit, factor
) -> None:
    """Test energy cost price from sensor entity."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: energy_unit,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
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
                    "number_energy_price": 0.5,
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

    # Initial state: 10kWh
    hass.states.async_set(
        "sensor.energy_consumption",
        10 * factor,
        energy_attributes,
    )

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Energy use bumped by 10 kWh
    hass.states.async_set(
        "sensor.energy_consumption",
        20 * factor,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "5.0"


@pytest.mark.parametrize(
    "price_unit,factor",
    [
        (f"EUR/{ENERGY_WATT_HOUR}", 0.001),
        (f"EUR/{ENERGY_KILO_WATT_HOUR}", 1),
        (f"EUR/{ENERGY_MEGA_WATT_HOUR}", 1000),
    ],
)
async def test_cost_sensor_handle_price_units(
    hass, hass_storage, setup_integration, price_unit, factor
) -> None:
    """Test energy cost price from sensor entity."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: price_unit,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    }
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
            "flow_to": [],
            "cost_adjustment_day": 0,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    now = dt_util.utcnow()

    # Initial state: 10kWh
    hass.states.async_set("sensor.energy_price", "2", price_attributes)
    hass.states.async_set(
        "sensor.energy_consumption",
        10 * factor,
        energy_attributes,
    )

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Energy use bumped by 10 kWh
    hass.states.async_set(
        "sensor.energy_consumption",
        20 * factor,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "20.0"


async def test_cost_sensor_handle_gas(hass, hass_storage, setup_integration) -> None:
    """Test gas cost price from sensor entity."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: VOLUME_CUBIC_METERS,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas_consumption",
            "entity_energy_from": "sensor.gas_consumption",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 0.5,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    now = dt_util.utcnow()

    hass.states.async_set(
        "sensor.gas_consumption",
        100,
        energy_attributes,
    )

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.gas_consumption_cost")
    assert state.state == "0.0"

    # gas use bumped to 10 kWh
    hass.states.async_set(
        "sensor.gas_consumption",
        200,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gas_consumption_cost")
    assert state.state == "50.0"


async def test_cost_sensor_handle_gas_kwh(
    hass, hass_storage, setup_integration
) -> None:
    """Test gas cost price from sensor entity."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas_consumption",
            "entity_energy_from": "sensor.gas_consumption",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 0.5,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    now = dt_util.utcnow()

    hass.states.async_set(
        "sensor.gas_consumption",
        100,
        energy_attributes,
    )

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.gas_consumption_cost")
    assert state.state == "0.0"

    # gas use bumped to 10 kWh
    hass.states.async_set(
        "sensor.gas_consumption",
        200,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gas_consumption_cost")
    assert state.state == "50.0"


@pytest.mark.parametrize("state_class", [None])
async def test_cost_sensor_wrong_state_class(
    hass, hass_storage, setup_integration, caplog, state_class
) -> None:
    """Test energy sensor rejects sensor with wrong state_class."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: state_class,
    }
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
                    "number_energy_price": 0.5,
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

    hass.states.async_set(
        "sensor.energy_consumption",
        10000,
        energy_attributes,
    )

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == STATE_UNKNOWN
    assert (
        f"Found unexpected state_class {state_class} for sensor.energy_consumption"
        in caplog.text
    )

    # Energy use bumped to 10 kWh
    hass.states.async_set(
        "sensor.energy_consumption",
        20000,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("state_class", [SensorStateClass.MEASUREMENT])
async def test_cost_sensor_state_class_measurement_no_reset(
    hass, hass_storage, setup_integration, caplog, state_class
) -> None:
    """Test energy sensor rejects state_class measurement with no last_reset."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_STATE_CLASS: state_class,
    }
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
                    "number_energy_price": 0.5,
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

    hass.states.async_set(
        "sensor.energy_consumption",
        10000,
        energy_attributes,
    )

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == STATE_UNKNOWN

    # Energy use bumped to 10 kWh
    hass.states.async_set(
        "sensor.energy_consumption",
        20000,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == STATE_UNKNOWN


async def test_inherit_source_unique_id(hass, hass_storage, setup_integration):
    """Test sensor inherits unique ID from source."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas_consumption",
            "entity_energy_from": "sensor.gas_consumption",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 0.5,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    now = dt_util.utcnow()
    entity_registry = er.async_get(hass)
    source_entry = entity_registry.async_get_or_create(
        "sensor", "test", "123456", suggested_object_id="gas_consumption"
    )

    hass.states.async_set(
        "sensor.gas_consumption",
        100,
        {
            ATTR_UNIT_OF_MEASUREMENT: VOLUME_CUBIC_METERS,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass)

    state = hass.states.get("sensor.gas_consumption_cost")
    assert state
    assert state.state == "0.0"

    entry = entity_registry.async_get("sensor.gas_consumption_cost")
    assert entry
    assert entry.unique_id == f"{source_entry.id}_gas_cost"
    assert entry.hidden_by is er.RegistryEntryHider.INTEGRATION
