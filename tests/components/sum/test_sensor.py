"""The test for the sum sensor platform."""
from __future__ import annotations

import pytest

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.components.sum.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

VALUES = [17, 20, 15.3]
VALUES_ERROR = [17, "a", 15.3]
UOM = ["kg", "kg", "hg"]
SUM_VALUE = sum(VALUES)


async def test_sum_sensor(hass: HomeAssistant):
    """Test the sum sensor."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "name": "My sum",
            "round_digits": 2.0,
        },
        title="My sum",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_ids = config_entry.options["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.my_sum")

    assert str(float(SUM_VALUE)) == state.state
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_incorrect_states(hass: HomeAssistant):
    """Test that returns state unknown on missing values."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "name": "My sum",
            "round_digits": 2.0,
        },
        title="My sum",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_ids = config_entry.options["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    hass.states.async_set(entity_ids[0], STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.my_sum")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(entity_ids[0], VALUES[0])
    await hass.async_block_till_done()

    state = hass.states.get("sensor.my_sum")
    assert STATE_UNKNOWN != state.state

    hass.states.async_set(entity_ids[1], STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.my_sum")
    assert state.state == STATE_UNKNOWN


async def test_sensor_different_uom(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """Test the sensor with different unit of measurements."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "name": "My sum",
            "round_digits": 2.0,
        },
        title="My sum",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_ids = config_entry.options["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value, {"unit_of_measurement": entity_id})
        await hass.async_block_till_done()

    log = caplog.text

    assert "Units of measurement do not match for entity" in log


async def test_sensor_incorrect_values(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """Test the sensor with different unit of measurements."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "name": "My sum",
            "round_digits": 2.0,
        },
        title="My sum",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_ids = config_entry.options["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES_ERROR)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    log = caplog.text

    assert "Unable to store state. Only numerical states are supported" in log


async def test_sum_sensor_from_yaml(hass: HomeAssistant):
    """Test the sum sensor setup from yaml."""
    config = {
        "sensor": {
            "platform": "sum",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
            "name": "My Sum",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.my_sum")

    assert str(float(SUM_VALUE)) == state.state
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
