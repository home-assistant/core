"""Test the Energy sensors."""

from collections.abc import Callable, Coroutine
import copy
from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.energy import async_get_manager, data
from homeassistant.components.energy.sensor import (
    EnergyCostSensor,
    EnergyPowerSensor,
    SensorManager,
    SourceAdapter,
)
from homeassistant.components.recorder.core import Recorder
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.sensor.recorder import (  # pylint: disable=hass-component-root-import
    compile_statistics,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import _WH_TO_CAL, _WH_TO_J
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done
from tests.typing import WebSocketGenerator

TEST_TIME_ADVANCE_INTERVAL = timedelta(milliseconds=10)


@pytest.fixture
async def setup_integration(
    recorder_mock: Recorder,
) -> Callable[[HomeAssistant], Coroutine[Any, Any, None]]:
    """Set up the integration."""

    async def setup_integration(hass: HomeAssistant) -> None:
        assert await async_setup_component(hass, "energy", {})
        await hass.async_block_till_done()

    return setup_integration


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Freeze clock for tests."""
    freezer.move_to("2022-04-19 07:53:05")
    return freezer


def get_statistics_for_entity(statistics_results, entity_id):
    """Get statistics for a certain entity, or None if there is none."""
    for statistics_result in statistics_results:
        if statistics_result["meta"]["statistic_id"] == entity_id:
            return statistics_result
    return None


async def test_cost_sensor_no_states(
    setup_integration, hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test sensors are created."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "foo",
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
    # pylint: disable-next=fixme
    # TODO: No states, should the cost entity refuse to setup?


async def test_cost_sensor_attributes(
    setup_integration,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test sensor attributes."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    cost_sensor_entity_id = "sensor.energy_consumption_cost"
    entry = entity_registry.async_get(cost_sensor_entity_id)
    assert entry.entity_category is None
    assert entry.disabled_by is None
    assert entry.hidden_by == er.RegistryEntryHider.INTEGRATION


@pytest.mark.parametrize(
    ("initial_energy", "initial_cost"), [(0, "0.0"), (None, "unknown")]
)
@pytest.mark.parametrize(
    ("price_entity", "fixed_price"), [("sensor.energy_price", None), (None, 1)]
)
@pytest.mark.parametrize(
    (
        "usage_sensor_entity_id",
        "cost_sensor_entity_id",
        "flow_type",
        "energy_source_data",
        "price_update_key",
    ),
    [
        (
            "sensor.energy_consumption",
            "sensor.energy_consumption_cost",
            "flow_from",
            {
                "type": "grid",
                "stat_energy_from": "sensor.energy_consumption",
                "cost_adjustment_day": 0,
            },
            "number_energy_price",
        ),
        (
            "sensor.energy_production",
            "sensor.energy_production_compensation",
            "flow_to",
            {
                "type": "grid",
                "stat_energy_to": "sensor.energy_production",
                "cost_adjustment_day": 0,
            },
            "number_energy_price_export",
        ),
    ],
)
async def test_cost_sensor_price_entity_total_increasing(
    frozen_time,
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    initial_energy,
    initial_cost,
    price_entity,
    fixed_price,
    usage_sensor_entity_id,
    cost_sensor_entity_id,
    flow_type,
    energy_source_data: dict[str, Any],
    price_update_key: str,
) -> None:
    """Test energy cost price from total_increasing type sensor entity."""

    def _compile_statistics(_):
        with session_scope(hass=hass) as session:
            return compile_statistics(
                hass, session, now, now + timedelta(seconds=1)
            ).platform_stats

    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }

    energy_data = data.EnergyManager.default_preferences()
    # Build energy source from test parameter data, adding price fields
    energy_source = copy.deepcopy(energy_source_data)
    if flow_type == "flow_from":
        energy_source["entity_energy_price"] = price_entity
        energy_source["number_energy_price"] = fixed_price
    else:
        energy_source["entity_energy_price_export"] = price_entity
        energy_source["number_energy_price_export"] = fixed_price
    energy_data["energy_sources"].append(energy_source)

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

    entry = entity_registry.async_get(cost_sensor_entity_id)
    assert entry
    postfix = "cost" if flow_type == "flow_from" else "compensation"
    assert entry.unique_id == f"{usage_sensor_entity_id}_grid_{postfix}"
    assert entry.hidden_by is er.RegistryEntryHider.INTEGRATION

    # Energy use bumped to 10 kWh
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
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
        energy_data["energy_sources"][0][price_update_key] = 2
        client = await hass_ws_client(hass)
        await client.send_json({"id": 5, "type": "energy/save_prefs", **energy_data})
        msg = await client.receive_json()
        assert msg["success"]
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 10 EUR + (10-10) kWh * 2 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Additional consumption is using the new price
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
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
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
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
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
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
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
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


@pytest.mark.parametrize(
    ("initial_energy", "initial_cost"), [(0, "0.0"), (None, "unknown")]
)
@pytest.mark.parametrize(
    ("price_entity", "fixed_price"), [("sensor.energy_price", None), (None, 1)]
)
@pytest.mark.parametrize(
    (
        "usage_sensor_entity_id",
        "cost_sensor_entity_id",
        "flow_type",
        "energy_source_data",
        "price_update_key",
    ),
    [
        (
            "sensor.energy_consumption",
            "sensor.energy_consumption_cost",
            "flow_from",
            {
                "type": "grid",
                "stat_energy_from": "sensor.energy_consumption",
                "cost_adjustment_day": 0,
            },
            "number_energy_price",
        ),
        (
            "sensor.energy_production",
            "sensor.energy_production_compensation",
            "flow_to",
            {
                "type": "grid",
                "stat_energy_to": "sensor.energy_production",
                "cost_adjustment_day": 0,
            },
            "number_energy_price_export",
        ),
    ],
)
@pytest.mark.parametrize("energy_state_class", ["total", "measurement"])
async def test_cost_sensor_price_entity_total(
    frozen_time,
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    initial_energy,
    initial_cost,
    price_entity,
    fixed_price,
    usage_sensor_entity_id,
    cost_sensor_entity_id,
    flow_type,
    energy_source_data: dict[str, Any],
    price_update_key: str,
    energy_state_class,
) -> None:
    """Test energy cost price from total type sensor entity."""

    def _compile_statistics(_):
        with session_scope(hass=hass) as session:
            return compile_statistics(
                hass, session, now, now + timedelta(seconds=0.17)
            ).platform_stats

    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        ATTR_STATE_CLASS: energy_state_class,
    }

    energy_data = data.EnergyManager.default_preferences()
    # Build energy source from test parameter data, adding price fields
    energy_source = copy.deepcopy(energy_source_data)
    if flow_type == "flow_from":
        energy_source["entity_energy_price"] = price_entity
        energy_source["number_energy_price"] = fixed_price
    else:
        energy_source["entity_energy_price_export"] = price_entity
        energy_source["number_energy_price_export"] = fixed_price
    energy_data["energy_sources"].append(energy_source)

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
            {**energy_attributes, "last_reset": last_reset},
        )
    hass.states.async_set("sensor.energy_price", "1")

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
        hass.states.async_set(
            usage_sensor_entity_id,
            "0",
            {**energy_attributes, "last_reset": last_reset},
        )
        await hass.async_block_till_done()

    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "0.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "EUR"

    entry = entity_registry.async_get(cost_sensor_entity_id)
    assert entry
    postfix = "cost" if flow_type == "flow_from" else "compensation"
    assert entry.unique_id == f"{usage_sensor_entity_id}_grid_{postfix}"
    assert entry.hidden_by is er.RegistryEntryHider.INTEGRATION

    # Energy use bumped to 10 kWh
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
    hass.states.async_set(
        usage_sensor_entity_id,
        "10",
        {**energy_attributes, "last_reset": last_reset},
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
        energy_data["energy_sources"][0][price_update_key] = 2
        client = await hass_ws_client(hass)
        await client.send_json({"id": 5, "type": "energy/save_prefs", **energy_data})
        msg = await client.receive_json()
        assert msg["success"]
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 10 EUR + (10-10) kWh * 2 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Additional consumption is using the new price
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
    hass.states.async_set(
        usage_sensor_entity_id,
        "14.5",
        {**energy_attributes, "last_reset": last_reset},
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
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
    hass.states.async_set(
        usage_sensor_entity_id,
        "14",
        {**energy_attributes, "last_reset": last_reset},
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "18.0"  # 19 EUR + (14-14.5) kWh * 2 EUR/kWh = 18 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Energy sensor is reset, with initial state at 4kWh, 0 kWh is used as zero-point
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
    last_reset = dt_util.utcnow()
    hass.states.async_set(
        usage_sensor_entity_id,
        "4",
        {**energy_attributes, "last_reset": last_reset},
    )
    await hass.async_block_till_done()
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "8.0"  # 0 EUR + (4-0) kWh * 2 EUR/kWh = 8 EUR
    assert state.attributes[ATTR_LAST_RESET] != last_reset_cost_sensor
    last_reset_cost_sensor = state.attributes[ATTR_LAST_RESET]

    # Energy use bumped to 10 kWh
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
    hass.states.async_set(
        usage_sensor_entity_id,
        "10",
        {**energy_attributes, "last_reset": last_reset},
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


@pytest.mark.parametrize(
    ("initial_energy", "initial_cost"), [(0, "0.0"), (None, "unknown")]
)
@pytest.mark.parametrize(
    ("price_entity", "fixed_price"), [("sensor.energy_price", None), (None, 1)]
)
@pytest.mark.parametrize(
    (
        "usage_sensor_entity_id",
        "cost_sensor_entity_id",
        "flow_type",
        "energy_source_data",
        "price_update_key",
    ),
    [
        (
            "sensor.energy_consumption",
            "sensor.energy_consumption_cost",
            "flow_from",
            {
                "type": "grid",
                "stat_energy_from": "sensor.energy_consumption",
                "cost_adjustment_day": 0,
            },
            "number_energy_price",
        ),
        (
            "sensor.energy_production",
            "sensor.energy_production_compensation",
            "flow_to",
            {
                "type": "grid",
                "stat_energy_to": "sensor.energy_production",
                "cost_adjustment_day": 0,
            },
            "number_energy_price_export",
        ),
    ],
)
@pytest.mark.parametrize("energy_state_class", ["total"])
async def test_cost_sensor_price_entity_total_no_reset(
    frozen_time,
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    initial_energy,
    initial_cost,
    price_entity,
    fixed_price,
    usage_sensor_entity_id,
    cost_sensor_entity_id,
    flow_type,
    energy_source_data: dict[str, Any],
    price_update_key: str,
    energy_state_class,
) -> None:
    """Test energy cost price from total type sensor entity with no last_reset."""

    def _compile_statistics(_):
        with session_scope(hass=hass) as session:
            return compile_statistics(
                hass, session, now, now + timedelta(seconds=1)
            ).platform_stats

    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        ATTR_STATE_CLASS: energy_state_class,
    }

    energy_data = data.EnergyManager.default_preferences()
    # Build energy source from test parameter data, adding price fields
    energy_source = copy.deepcopy(energy_source_data)
    if flow_type == "flow_from":
        energy_source["entity_energy_price"] = price_entity
        energy_source["number_energy_price"] = fixed_price
    else:
        energy_source["entity_energy_price_export"] = price_entity
        energy_source["number_energy_price_export"] = fixed_price
    energy_data["energy_sources"].append(energy_source)

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

    entry = entity_registry.async_get(cost_sensor_entity_id)
    assert entry
    postfix = "cost" if flow_type == "flow_from" else "compensation"
    assert entry.unique_id == f"{usage_sensor_entity_id}_grid_{postfix}"
    assert entry.hidden_by is er.RegistryEntryHider.INTEGRATION

    # Energy use bumped to 10 kWh
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
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
        energy_data["energy_sources"][0][price_update_key] = 2
        client = await hass_ws_client(hass)
        await client.send_json({"id": 5, "type": "energy/save_prefs", **energy_data})
        msg = await client.receive_json()
        assert msg["success"]
    state = hass.states.get(cost_sensor_entity_id)
    assert state.state == "10.0"  # 10 EUR + (10-10) kWh * 2 EUR/kWh = 10 EUR
    assert state.attributes[ATTR_LAST_RESET] == last_reset_cost_sensor

    # Additional consumption is using the new price
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
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
    frozen_time.tick(TEST_TIME_ADVANCE_INTERVAL)
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
    ("energy_unit", "factor"),
    [
        (UnitOfEnergy.MILLIWATT_HOUR, 1e6),
        (UnitOfEnergy.WATT_HOUR, 1000),
        (UnitOfEnergy.KILO_WATT_HOUR, 1),
        (UnitOfEnergy.MEGA_WATT_HOUR, 0.001),
        (UnitOfEnergy.GIGA_JOULE, _WH_TO_J / 1e6),
        (UnitOfEnergy.CALORIE, _WH_TO_CAL * 1e3),
    ],
)
async def test_cost_sensor_handle_energy_units(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    energy_unit,
    factor,
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

    # Initial state: 10kWh
    hass.states.async_set(
        "sensor.energy_consumption",
        10 * factor,
        energy_attributes,
    )

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
    ("price_unit", "factor"),
    [
        (f"EUR/{UnitOfEnergy.MILLIWATT_HOUR}", 1e-6),
        (f"EUR/{UnitOfEnergy.WATT_HOUR}", 0.001),
        (f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}", 1),
        (f"EUR/{UnitOfEnergy.MEGA_WATT_HOUR}", 1000),
        (f"EUR/{UnitOfEnergy.GIGA_JOULE}", 1000 / 3.6),
    ],
)
async def test_cost_sensor_handle_price_units(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    price_unit,
    factor,
) -> None:
    """Test energy cost price from sensor entity."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
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

    # Initial state: 10kWh
    hass.states.async_set("sensor.energy_price", "2", price_attributes)
    hass.states.async_set(
        "sensor.energy_consumption",
        10 * factor,
        energy_attributes,
    )

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


async def test_cost_sensor_handle_late_price_sensor(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test energy cost where the price sensor is not immediately available."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
    price_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}",
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    }
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    # Initial state: 10kWh, price sensor not yet available
    hass.states.async_set("sensor.energy_price", "unknown", price_attributes)
    hass.states.async_set(
        "sensor.energy_consumption",
        10,
        energy_attributes,
    )

    await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Energy use bumped by 10 kWh, price sensor still not yet available
    hass.states.async_set(
        "sensor.energy_consumption",
        20,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Energy use bumped by 10 kWh, price sensor now available
    hass.states.async_set("sensor.energy_price", "1", price_attributes)
    hass.states.async_set(
        "sensor.energy_consumption",
        30,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "20.0"

    # Energy use bumped by 10 kWh, price sensor available
    hass.states.async_set(
        "sensor.energy_consumption",
        40,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "30.0"

    # Energy use bumped by 10 kWh, price sensor no longer available
    hass.states.async_set("sensor.energy_price", "unknown", price_attributes)
    hass.states.async_set(
        "sensor.energy_consumption",
        50,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "30.0"

    # Energy use bumped by 10 kWh, price sensor again available
    hass.states.async_set("sensor.energy_price", "2", price_attributes)
    hass.states.async_set(
        "sensor.energy_consumption",
        60,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "70.0"


@pytest.mark.parametrize(
    "unit",
    [UnitOfVolume.CUBIC_FEET, UnitOfVolume.CUBIC_METERS, UnitOfVolume.LITERS],
)
async def test_cost_sensor_handle_gas(
    setup_integration, hass: HomeAssistant, hass_storage: dict[str, Any], unit
) -> None:
    """Test gas cost price from sensor entity."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: unit,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas_consumption",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 0.5,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    hass.states.async_set(
        "sensor.gas_consumption",
        100,
        energy_attributes,
    )

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
    setup_integration, hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test gas cost price from sensor entity."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas_consumption",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 0.5,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    hass.states.async_set(
        "sensor.gas_consumption",
        100,
        energy_attributes,
    )

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


@pytest.mark.parametrize(
    ("unit_system", "usage_unit", "growth"),
    [
        # 1 cubic foot = 7.47 gl, 100 ft3 growth @ 0.5/ft3:
        (US_CUSTOMARY_SYSTEM, UnitOfVolume.CUBIC_FEET, 374.025974025974),
        (US_CUSTOMARY_SYSTEM, UnitOfVolume.GALLONS, 50.0),
        (METRIC_SYSTEM, UnitOfVolume.CUBIC_METERS, 50.0),
    ],
)
async def test_cost_sensor_handle_water(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    unit_system,
    usage_unit,
    growth,
) -> None:
    """Test water cost price from sensor entity."""
    hass.config.units = unit_system
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: usage_unit,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
    }
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "water",
            "stat_energy_from": "sensor.water_consumption",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 0.5,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    hass.states.async_set(
        "sensor.water_consumption",
        100,
        energy_attributes,
    )

    await setup_integration(hass)

    state = hass.states.get("sensor.water_consumption_cost")
    assert state.state == "0.0"

    # water use bumped to 200 ft³/m³
    hass.states.async_set(
        "sensor.water_consumption",
        200,
        energy_attributes,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.water_consumption_cost")
    assert float(state.state) == pytest.approx(growth)


@pytest.mark.parametrize("state_class", [None])
async def test_cost_sensor_wrong_state_class(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    state_class,
) -> None:
    """Test energy sensor rejects sensor with wrong state_class."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        ATTR_STATE_CLASS: state_class,
    }
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    hass.states.async_set(
        "sensor.energy_consumption",
        10000,
        energy_attributes,
    )

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
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    state_class,
) -> None:
    """Test energy sensor rejects state_class measurement with no last_reset."""
    energy_attributes = {
        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        ATTR_STATE_CLASS: state_class,
    }
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    hass.states.async_set(
        "sensor.energy_consumption",
        10000,
        energy_attributes,
    )

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


async def test_inherit_source_unique_id(
    setup_integration,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test sensor inherits unique ID from source."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "gas",
            "stat_energy_from": "sensor.gas_consumption",
            "stat_cost": None,
            "entity_energy_price": None,
            "number_energy_price": 0.5,
        }
    )

    hass_storage[data.STORAGE_KEY] = {
        "version": 1,
        "data": energy_data,
    }

    source_entry = entity_registry.async_get_or_create(
        "sensor", "test", "123456", suggested_object_id="gas_consumption"
    )

    hass.states.async_set(
        "sensor.gas_consumption",
        100,
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.CUBIC_METERS,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )

    await setup_integration(hass)

    state = hass.states.get("sensor.gas_consumption_cost")
    assert state
    assert state.state == "0.0"

    entry = entity_registry.async_get("sensor.gas_consumption_cost")
    assert entry
    assert entry.unique_id == f"{source_entry.id}_gas_cost"
    assert entry.hidden_by is er.RegistryEntryHider.INTEGRATION


async def test_needs_power_sensor_standard(hass: HomeAssistant) -> None:
    """Test _needs_power_sensor returns False for standard stat_rate."""
    assert SensorManager._needs_power_sensor({"stat_rate": "sensor.power"}) is False


async def test_needs_power_sensor_inverted(hass: HomeAssistant) -> None:
    """Test _needs_power_sensor returns True for inverted config."""
    assert (
        SensorManager._needs_power_sensor({"stat_rate_inverted": "sensor.power"})
        is True
    )


async def test_needs_power_sensor_combined(hass: HomeAssistant) -> None:
    """Test _needs_power_sensor returns True for combined config."""
    assert (
        SensorManager._needs_power_sensor(
            {
                "stat_rate_from": "sensor.discharge",
                "stat_rate_to": "sensor.charge",
            }
        )
        is True
    )


async def test_needs_power_sensor_partial_combined(hass: HomeAssistant) -> None:
    """Test _needs_power_sensor returns False for incomplete combined config."""
    # Only stat_rate_from without stat_rate_to
    assert (
        SensorManager._needs_power_sensor({"stat_rate_from": "sensor.discharge"})
        is False
    )


async def test_power_sensor_manager_creation(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test SensorManager creates power sensors correctly."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up a source sensor
    hass.states.async_set(
        "sensor.battery_power",
        "100.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor entity was created
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert float(state.state) == -100.0


async def test_power_sensor_manager_cleanup(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test SensorManager removes power sensors when config changes."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensors
    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    # Create with inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify sensor exists and has a valid value
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert state.state == "-100.0"

    # Update to remove power_config (use direct stat_rate)
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "stat_rate": "sensor.battery_power",
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify sensor becomes unavailable when entity is removed
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert state.state == "unavailable"


async def test_power_sensor_grid_combined(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test power sensor for grid with combined config."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensors
    hass.states.async_set(
        "sensor.grid_import",
        "500.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    hass.states.async_set(
        "sensor.grid_export",
        "200.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with grid that has combined power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "grid",
                    "stat_energy_from": "sensor.grid_energy_import",
                    "stat_energy_to": "sensor.grid_energy_export",
                    "power_config": {
                        "stat_rate_from": "sensor.grid_import",
                        "stat_rate_to": "sensor.grid_export",
                    },
                    "cost_adjustment_day": 0,
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor entity was created
    state = hass.states.get("sensor.energy_grid_grid_import_grid_export_net_power")
    assert state is not None
    # 500 - 200 = 300 (net import)
    assert float(state.state) == 300.0


async def test_power_sensor_device_assignment(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test power sensor is assigned to same device as source sensor."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Create a config entry for the device
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    # Create a device and register source sensor to it
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "battery_device")},
        name="Battery Device",
    )

    # Register the source sensor with the device
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_power",
        suggested_object_id="battery_power",
        device_id=device_entry.id,
    )

    # Set up source sensor state
    hass.states.async_set(
        "sensor.battery_power",
        "100.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor was created and assigned to same device
    power_sensor_entry = entity_registry.async_get("sensor.battery_power_inverted")
    assert power_sensor_entry is not None
    assert power_sensor_entry.device_id == device_entry.id


async def test_power_sensor_device_assignment_combined_second_sensor(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test power sensor checks second sensor if first has no device."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Create a config entry for the device
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    # Create a device and register second sensor to it
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "battery_device")},
        name="Battery Device",
    )

    # Register first sensor WITHOUT device
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_discharge",
        suggested_object_id="battery_discharge",
    )

    # Register second sensor WITH device
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_charge",
        suggested_object_id="battery_charge",
        device_id=device_entry.id,
    )

    # Set up source sensor states
    hass.states.async_set(
        "sensor.battery_discharge",
        "100.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "50.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has combined power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_from": "sensor.battery_discharge",
                        "stat_rate_to": "sensor.battery_charge",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor was created and assigned to second sensor's device
    power_sensor_entry = entity_registry.async_get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert power_sensor_entry is not None
    assert power_sensor_entry.device_id == device_entry.id


async def test_power_sensor_inverted_availability(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test inverted power sensor availability follows source sensor."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensor as available
    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    # Configure battery with inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Power sensor should be available
    state = hass.states.get("sensor.battery_power_inverted")
    assert state
    assert state.state == "-100.0"

    # Make source unavailable
    hass.states.async_set("sensor.battery_power", "unavailable")
    await hass.async_block_till_done()

    # Power sensor should become unavailable
    state = hass.states.get("sensor.battery_power_inverted")
    assert state
    assert state.state == "unavailable"

    # Make source available again
    hass.states.async_set("sensor.battery_power", "50.0")
    await hass.async_block_till_done()

    # Power sensor should become available again
    state = hass.states.get("sensor.battery_power_inverted")
    assert state
    assert state.state == "-50.0"


async def test_power_sensor_combined_availability(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test combined power sensor availability requires both sources available."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up both source sensors as available
    hass.states.async_set("sensor.battery_discharge", "150.0")
    hass.states.async_set("sensor.battery_charge", "50.0")
    await hass.async_block_till_done()

    # Configure battery with combined power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_from": "sensor.battery_discharge",
                        "stat_rate_to": "sensor.battery_charge",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Power sensor should be available and show net power
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state
    assert state.state == "100.0"

    # Make first source unavailable
    hass.states.async_set("sensor.battery_discharge", "unavailable")
    await hass.async_block_till_done()

    # Power sensor should become unavailable
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state
    assert state.state == "unavailable"

    # Make first source available again
    hass.states.async_set("sensor.battery_discharge", "200.0")
    await hass.async_block_till_done()

    # Power sensor should become available again
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state
    assert state.state == "150.0"

    # Make second source unavailable
    hass.states.async_set("sensor.battery_charge", "unknown")
    await hass.async_block_till_done()

    # Power sensor should become unavailable again
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state
    assert state.state == "unavailable"


async def test_power_sensor_battery_combined(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test power sensor for battery with combined config."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensors
    hass.states.async_set(
        "sensor.battery_discharge",
        "150.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "50.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has combined power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_from": "sensor.battery_discharge",
                        "stat_rate_to": "sensor.battery_charge",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor entity was created
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state is not None
    # 150 - 50 = 100 (net discharging)
    assert float(state.state) == 100.0

    # Test net charging scenario
    hass.states.async_set("sensor.battery_discharge", "30.0")
    hass.states.async_set("sensor.battery_charge", "80.0")
    await hass.async_block_till_done()

    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state is not None
    # 30 - 80 = -50 (net charging)
    assert float(state.state) == -50.0


async def test_power_sensor_combined_unit_conversion(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test power sensor combined mode with different units."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensors with different units (kW and W)
    hass.states.async_set(
        "sensor.battery_discharge",
        "1.5",  # 1.5 kW = 1500 W
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
    )
    hass.states.async_set(
        "sensor.battery_charge",
        "500.0",  # 500 W
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has combined power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_from": "sensor.battery_discharge",
                        "stat_rate_to": "sensor.battery_charge",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor converts units properly
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state is not None
    # 1500 W - 500 W = 1000 W (units are converted to W internally)
    assert float(state.state) == 1000.0


async def test_power_sensor_inverted_negative_values(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test inverted power sensor with negative source values."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensor with positive value
    hass.states.async_set(
        "sensor.battery_power",
        "100.0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    )
    await hass.async_block_till_done()

    # Update with battery that has inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify inverted value
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert float(state.state) == -100.0

    # Update source to negative value (should become positive)
    hass.states.async_set("sensor.battery_power", "-50.0")
    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert float(state.state) == 50.0


async def test_energy_data_removal(
    recorder_mock: Recorder, hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that cost sensors are removed when energy data is cleared."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    hass.states.async_set(
        "sensor.energy_consumption",
        "100",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )

    assert await async_setup_component(hass, "energy", {"energy": {}})
    await hass.async_block_till_done()

    # Verify cost sensor was created
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state is not None
    assert state.state == "0.0"

    # Clear all energy data
    manager = await async_get_manager(hass)
    await manager.async_update({"energy_sources": []})
    await hass.async_block_till_done()

    # Verify cost sensor becomes unavailable
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state is not None
    assert state.state == "unavailable"


async def test_stat_cost_already_configured(
    setup_integration, hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that no cost sensor is created when stat_cost is already configured."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
                    "stat_cost": "sensor.existing_cost",  # Cost already configured
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

    hass.states.async_set(
        "sensor.energy_consumption",
        "100",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )
    hass.states.async_set("sensor.existing_cost", "50.0")

    await setup_integration(hass)

    # Verify no cost sensor was created (since stat_cost is configured)
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state is None


async def test_invalid_energy_state(
    setup_integration, hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test handling of invalid energy state value."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    # Set energy sensor with valid initial state
    hass.states.async_set(
        "sensor.energy_consumption",
        "100",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )

    await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Update with invalid value
    hass.states.async_set(
        "sensor.energy_consumption",
        "not_a_number",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )
    await hass.async_block_till_done()

    # Cost should remain unchanged
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"


async def test_invalid_energy_unit(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of invalid energy unit."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    # Set energy sensor with valid state
    hass.states.async_set(
        "sensor.energy_consumption",
        "100",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )

    await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Update with invalid unit
    hass.states.async_set(
        "sensor.energy_consumption",
        "200",
        {
            ATTR_UNIT_OF_MEASUREMENT: "invalid_unit",
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )
    await hass.async_block_till_done()

    # Cost should remain unchanged and warning should be logged
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"
    assert "Found unexpected unit invalid_unit" in caplog.text

    # Update again with same invalid unit - should not log again
    caplog.clear()
    hass.states.async_set(
        "sensor.energy_consumption",
        "300",
        {
            ATTR_UNIT_OF_MEASUREMENT: "invalid_unit",
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )
    await hass.async_block_till_done()

    # No new warning should be logged (already warned once)
    assert "Found unexpected unit" not in caplog.text


async def test_no_energy_unit(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of missing energy unit."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    # Set energy sensor with valid state
    hass.states.async_set(
        "sensor.energy_consumption",
        "100",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )

    await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Update with no unit
    hass.states.async_set(
        "sensor.energy_consumption",
        "200",
        {ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING},
    )
    await hass.async_block_till_done()

    # Cost should remain unchanged and warning should be logged
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"
    assert "Found unexpected unit None" in caplog.text


async def test_power_sensor_inverted_invalid_value(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test inverted power sensor with invalid source value."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensor with valid value
    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    # Configure battery with inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Power sensor should be available
    state = hass.states.get("sensor.battery_power_inverted")
    assert state
    assert state.state == "-100.0"

    # Update source to invalid value
    hass.states.async_set("sensor.battery_power", "not_a_number")
    await hass.async_block_till_done()

    # Power sensor should have unknown state (value is None)
    state = hass.states.get("sensor.battery_power_inverted")
    assert state
    assert state.state == "unknown"


async def test_power_sensor_combined_invalid_value(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test combined power sensor with invalid source value."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up both source sensors as valid
    hass.states.async_set("sensor.battery_discharge", "150.0")
    hass.states.async_set("sensor.battery_charge", "50.0")
    await hass.async_block_till_done()

    # Configure battery with combined power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_from": "sensor.battery_discharge",
                        "stat_rate_to": "sensor.battery_charge",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Power sensor should be available
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state
    assert state.state == "100.0"

    # Update first source to invalid value
    hass.states.async_set("sensor.battery_discharge", "invalid")
    await hass.async_block_till_done()

    # Power sensor should have unknown state (value is None)
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state
    assert state.state == "unknown"

    # Restore first source
    hass.states.async_set("sensor.battery_discharge", "150.0")
    await hass.async_block_till_done()

    # Power sensor should work again
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state
    assert state.state == "100.0"

    # Make second source invalid
    hass.states.async_set("sensor.battery_charge", "not_a_number")
    await hass.async_block_till_done()

    # Power sensor should have unknown state
    state = hass.states.get(
        "sensor.energy_battery_battery_discharge_battery_charge_net_power"
    )
    assert state
    assert state.state == "unknown"


async def test_power_sensor_naming_fallback(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test power sensor naming when source not in registry."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Set up source sensor WITHOUT registering it in entity registry
    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    # Configure battery with inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify sensor was created with fallback naming
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    # Name should be based on entity_id since not in registry
    assert state.attributes["friendly_name"] == "Battery Power Inverted"


async def test_power_sensor_no_device_assignment(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test power sensor when source sensors have no device."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Register source sensors WITHOUT device
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_power",
        suggested_object_id="battery_power",
    )

    # Set up source sensor state
    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    # Update with battery that has inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify the power sensor was created without device
    power_sensor_entry = entity_registry.async_get("sensor.battery_power_inverted")
    assert power_sensor_entry is not None
    assert power_sensor_entry.device_id is None


async def test_power_sensor_keeps_existing_on_update(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test that existing power sensor is kept when config doesn't change."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    # Create initial config
    config = {
        "energy_sources": [
            {
                "type": "battery",
                "stat_energy_from": "sensor.battery_energy_from",
                "stat_energy_to": "sensor.battery_energy_to",
                "power_config": {
                    "stat_rate_inverted": "sensor.battery_power",
                },
            }
        ],
    }
    await manager.async_update(config)
    await hass.async_block_till_done()

    # Verify power sensor exists
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert state.state == "-100.0"

    # Update source value
    hass.states.async_set("sensor.battery_power", "200.0")
    await hass.async_block_till_done()

    # Update manager with same config (should keep existing sensor)
    await manager.async_update(config)
    await hass.async_block_till_done()

    # Verify sensor still exists with updated value
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert state.state == "-200.0"


async def test_invalid_price_entity_value(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test handling of invalid energy price entity value."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
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

    # Set up energy sensor
    hass.states.async_set(
        "sensor.energy_consumption",
        "100",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )

    # Set up price sensor with invalid value
    hass.states.async_set("sensor.energy_price", "not_a_number")

    await setup_integration(hass)

    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Update energy consumption - cost should not change due to invalid price
    hass.states.async_set(
        "sensor.energy_consumption",
        "200",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )
    await hass.async_block_till_done()

    # Cost should remain at 0.0 because price is invalid
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"


async def test_power_sensor_naming_with_registry_name(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test power sensor naming uses registry name when available."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()

    # Register source sensor WITH a name
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "battery_power",
        suggested_object_id="battery_power",
        original_name="My Battery Power",
    )

    # Set up source sensor state
    hass.states.async_set("sensor.battery_power", "100.0")
    await hass.async_block_till_done()

    # Configure battery with inverted power_config
    await manager.async_update(
        {
            "energy_sources": [
                {
                    "type": "battery",
                    "stat_energy_from": "sensor.battery_energy_from",
                    "stat_energy_to": "sensor.battery_energy_to",
                    "power_config": {
                        "stat_rate_inverted": "sensor.battery_power",
                    },
                }
            ],
        }
    )
    await hass.async_block_till_done()

    # Verify sensor was created with registry name
    state = hass.states.get("sensor.battery_power_inverted")
    assert state is not None
    assert state.attributes["friendly_name"] == "My Battery Power Inverted"


async def test_missing_price_entity(
    setup_integration,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test handling when energy price entity doesn't exist."""
    energy_data = data.EnergyManager.default_preferences()
    energy_data["energy_sources"].append(
        {
            "type": "grid",
            "flow_from": [
                {
                    "stat_energy_from": "sensor.energy_consumption",
                    "stat_cost": None,
                    "entity_energy_price": "sensor.nonexistent_price",
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

    # Set up energy sensor only (price sensor doesn't exist)
    hass.states.async_set(
        "sensor.energy_consumption",
        "100",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )

    await setup_integration(hass)

    # When price entity doesn't exist initially, sensor stays unknown
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == STATE_UNKNOWN

    # Now create the price entity
    hass.states.async_set("sensor.nonexistent_price", "1.5")
    await hass.async_block_till_done()

    # Update energy consumption - should initialize now that price exists
    hass.states.async_set(
        "sensor.energy_consumption",
        "200",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )
    await hass.async_block_till_done()

    # Cost should be initialized (0.0 because it's the first update after price became available)
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "0.0"

    # Update consumption again - now cost should increase
    hass.states.async_set(
        "sensor.energy_consumption",
        "300",
        {
            ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )
    await hass.async_block_till_done()

    # Cost should be 150.0 (100 kWh * 1.5 EUR/kWh)
    state = hass.states.get("sensor.energy_consumption_cost")
    assert state.state == "150.0"


async def test_energy_cost_sensor_add_to_platform_abort(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test EnergyCostSensor.add_to_platform_abort sets the future."""
    adapter = SourceAdapter(
        source_type="grid",
        flow_type="flow_from",
        stat_energy_key="stat_energy_from",
        total_money_key="stat_cost",
        name_suffix="Cost",
        entity_id_suffix="cost",
    )
    config = {
        "stat_energy_from": "sensor.energy",
        "stat_cost": None,
        "entity_energy_price": "sensor.price",
        "number_energy_price": None,
    }

    sensor = EnergyCostSensor(adapter, config)

    # Future should not be done yet
    assert not sensor.add_finished.done()

    # Call abort
    sensor.add_to_platform_abort()

    # Future should now be done
    assert sensor.add_finished.done()


async def test_energy_power_sensor_add_to_platform_abort(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test EnergyPowerSensor.add_to_platform_abort sets the future."""
    sensor = EnergyPowerSensor(
        source_type="battery",
        config={"stat_rate_inverted": "sensor.battery_power"},
        unique_id="test_unique_id",
        entity_id="sensor.test_power",
    )

    # Future should not be done yet
    assert not sensor.add_finished.done()

    # Call abort
    sensor.add_to_platform_abort()

    # Future should now be done
    assert sensor.add_finished.done()
