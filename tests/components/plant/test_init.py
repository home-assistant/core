"""Unit tests for platform/plant.py."""

from datetime import datetime, timedelta

from homeassistant.components import plant
from homeassistant.components.recorder import Recorder
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONDUCTIVITY,
    LIGHT_LUX,
    STATE_OK,
    STATE_PROBLEM,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component

from tests.components.recorder.common import async_wait_recording_done

GOOD_DATA = {
    "moisture": 50,
    "battery": 90,
    "temperature": 23.4,
    "conductivity": 777,
    "brightness": 987,
}

BRIGHTNESS_ENTITY = "sensor.mqtt_plant_brightness"
MOISTURE_ENTITY = "sensor.mqtt_plant_moisture"

GOOD_CONFIG = {
    "sensors": {
        "moisture": MOISTURE_ENTITY,
        "battery": "sensor.mqtt_plant_battery",
        "temperature": "sensor.mqtt_plant_temperature",
        "conductivity": "sensor.mqtt_plant_conductivity",
        "brightness": BRIGHTNESS_ENTITY,
    },
    "min_moisture": 20,
    "max_moisture": 60,
    "min_battery": 17,
    "min_conductivity": 500,
    "min_temperature": 15,
    "min_brightness": 500,
}


async def test_valid_data(hass: HomeAssistant) -> None:
    """Test processing valid data."""
    sensor = plant.Plant("my plant", GOOD_CONFIG)
    sensor.entity_id = "sensor.mqtt_plant_battery"
    sensor.hass = hass
    for reading, value in GOOD_DATA.items():
        sensor.state_changed(
            GOOD_CONFIG["sensors"][reading],
            State(GOOD_CONFIG["sensors"][reading], value),
        )
    assert sensor.state == "ok"
    attrib = sensor.extra_state_attributes
    for reading, value in GOOD_DATA.items():
        # battery level has a different name in
        # the JSON format than in hass
        assert attrib[reading] == value


async def test_low_battery(hass: HomeAssistant) -> None:
    """Test processing with low battery data and limit set."""
    sensor = plant.Plant("other plant", GOOD_CONFIG)
    sensor.entity_id = "sensor.mqtt_plant_battery"
    sensor.hass = hass
    assert sensor.extra_state_attributes["problem"] == "none"
    sensor.state_changed(
        "sensor.mqtt_plant_battery",
        State("sensor.mqtt_plant_battery", 10),
    )
    assert sensor.state == "problem"
    assert sensor.extra_state_attributes["problem"] == "battery low"


async def test_initial_states(hass: HomeAssistant) -> None:
    """Test plant initialises attributes if sensor already exists."""
    hass.states.async_set(MOISTURE_ENTITY, 5, {ATTR_UNIT_OF_MEASUREMENT: CONDUCTIVITY})
    plant_name = "some_plant"
    assert await async_setup_component(
        hass, plant.DOMAIN, {plant.DOMAIN: {plant_name: GOOD_CONFIG}}
    )
    await hass.async_block_till_done()
    state = hass.states.get(f"plant.{plant_name}")
    assert state.attributes[plant.READING_MOISTURE] == 5


async def test_update_states(hass: HomeAssistant) -> None:
    """Test updating the state of a sensor.

    Make sure that plant processes this correctly.
    """
    plant_name = "some_plant"
    assert await async_setup_component(
        hass, plant.DOMAIN, {plant.DOMAIN: {plant_name: GOOD_CONFIG}}
    )
    hass.states.async_set(MOISTURE_ENTITY, 5, {ATTR_UNIT_OF_MEASUREMENT: CONDUCTIVITY})
    await hass.async_block_till_done()
    state = hass.states.get(f"plant.{plant_name}")
    assert state.state == STATE_PROBLEM
    assert state.attributes[plant.READING_MOISTURE] == 5


async def test_unavailable_state(hass: HomeAssistant) -> None:
    """Test updating the state with unavailable.

    Make sure that plant processes this correctly.
    """
    plant_name = "some_plant"
    assert await async_setup_component(
        hass, plant.DOMAIN, {plant.DOMAIN: {plant_name: GOOD_CONFIG}}
    )
    hass.states.async_set(
        MOISTURE_ENTITY, STATE_UNAVAILABLE, {ATTR_UNIT_OF_MEASUREMENT: CONDUCTIVITY}
    )
    await hass.async_block_till_done()
    state = hass.states.get(f"plant.{plant_name}")
    assert state.state == STATE_PROBLEM
    assert state.attributes[plant.READING_MOISTURE] == STATE_UNAVAILABLE


async def test_state_problem_if_unavailable(hass: HomeAssistant) -> None:
    """Test updating the state with unavailable after setting it to valid value.

    Make sure that plant processes this correctly.
    """
    plant_name = "some_plant"
    assert await async_setup_component(
        hass, plant.DOMAIN, {plant.DOMAIN: {plant_name: GOOD_CONFIG}}
    )
    hass.states.async_set(MOISTURE_ENTITY, 42, {ATTR_UNIT_OF_MEASUREMENT: CONDUCTIVITY})
    await hass.async_block_till_done()
    state = hass.states.get(f"plant.{plant_name}")
    assert state.state == STATE_OK
    assert state.attributes[plant.READING_MOISTURE] == 42
    hass.states.async_set(
        MOISTURE_ENTITY, STATE_UNAVAILABLE, {ATTR_UNIT_OF_MEASUREMENT: CONDUCTIVITY}
    )
    await hass.async_block_till_done()
    state = hass.states.get(f"plant.{plant_name}")
    assert state.state == STATE_PROBLEM
    assert state.attributes[plant.READING_MOISTURE] == STATE_UNAVAILABLE


async def test_load_from_db(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test bootstrapping the brightness history from the database.

    This test can should only be executed if the loading of the history
    is enabled via plant.ENABLE_LOAD_HISTORY.
    """
    plant_name = "wise_plant"
    for value in [20, 30, 10]:
        hass.states.async_set(
            BRIGHTNESS_ENTITY, value, {ATTR_UNIT_OF_MEASUREMENT: "Lux"}
        )
        await hass.async_block_till_done()
    # wait for the recorder to really store the data
    await async_wait_recording_done(hass)

    assert await async_setup_component(
        hass, plant.DOMAIN, {plant.DOMAIN: {plant_name: GOOD_CONFIG}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"plant.{plant_name}")
    assert state.state == STATE_PROBLEM
    max_brightness = state.attributes.get(plant.ATTR_MAX_BRIGHTNESS_HISTORY)
    assert max_brightness == 30


async def test_brightness_history(hass: HomeAssistant) -> None:
    """Test the min_brightness check."""
    plant_name = "some_plant"
    assert await async_setup_component(
        hass, plant.DOMAIN, {plant.DOMAIN: {plant_name: GOOD_CONFIG}}
    )
    hass.states.async_set(BRIGHTNESS_ENTITY, 100, {ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX})
    await hass.async_block_till_done()
    state = hass.states.get(f"plant.{plant_name}")
    assert state.state == STATE_PROBLEM

    hass.states.async_set(BRIGHTNESS_ENTITY, 600, {ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX})
    await hass.async_block_till_done()
    state = hass.states.get(f"plant.{plant_name}")
    assert state.state == STATE_OK

    hass.states.async_set(BRIGHTNESS_ENTITY, 100, {ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX})
    await hass.async_block_till_done()
    state = hass.states.get(f"plant.{plant_name}")
    assert state.state == STATE_OK


def test_daily_history_no_data(hass: HomeAssistant) -> None:
    """Test with empty history."""
    dh = plant.DailyHistory(3)
    assert dh.max is None


def test_daily_history_one_day(hass: HomeAssistant) -> None:
    """Test storing data for the same day."""
    dh = plant.DailyHistory(3)
    values = [-2, 10, 0, 5, 20]
    for i in range(len(values)):
        dh.add_measurement(values[i])
        max_value = max(values[0 : i + 1])
        assert len(dh._days) == 1
        assert dh.max == max_value


def test_daily_history_multiple_days(hass: HomeAssistant) -> None:
    """Test storing data for different days."""
    dh = plant.DailyHistory(3)
    today = datetime.now()
    today_minus_1 = today - timedelta(days=1)
    today_minus_2 = today_minus_1 - timedelta(days=1)
    today_minus_3 = today_minus_2 - timedelta(days=1)
    days = [today_minus_3, today_minus_2, today_minus_1, today]
    values = [10, 1, 7, 3]
    max_values = [10, 10, 10, 7]

    for i in range(len(days)):
        dh.add_measurement(values[i], days[i])
        assert max_values[i] == dh.max
