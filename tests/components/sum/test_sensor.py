"""The test for the sum sensor platform."""
from __future__ import annotations

import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.components.sum.const import DOMAIN
from homeassistant.components.sum.sensor import (
    ATTR_COUNT_VALID,
    ATTR_ENTITIES,
    ATTR_VALID_ENTITIES,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import SUM_VALUE, UOM, VALUES, VALUES_ERROR

from tests.common import MockConfigEntry


async def test_sum_sensor(hass: HomeAssistant) -> None:
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
    assert state.attributes.get(ATTR_ENTITIES) == [
        "sensor.test_1",
        "sensor.test_2",
        "sensor.test_3",
    ]
    assert state.attributes.get(ATTR_VALID_ENTITIES) == [
        "sensor.test_1",
        "sensor.test_2",
        "sensor.test_3",
    ]


async def test_incorrect_states(hass: HomeAssistant) -> None:
    """Test that returns state when missing correct values on entities."""
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
    assert state.state == "35.3"
    assert state.attributes.get(ATTR_ENTITIES) == [
        "sensor.test_1",
        "sensor.test_2",
        "sensor.test_3",
    ]
    assert state.attributes.get(ATTR_VALID_ENTITIES) == [
        "sensor.test_2",
        "sensor.test_3",
    ]

    hass.states.async_set(entity_ids[0], VALUES[0])
    await hass.async_block_till_done()

    state = hass.states.get("sensor.my_sum")
    assert state.state == "52.3"

    hass.states.async_set(entity_ids[1], STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.my_sum")
    assert state.state == "32.3"


async def test_sensor_different_uom(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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

    hass.states.async_set(entity_ids[0], VALUES[0], {ATTR_UNIT_OF_MEASUREMENT: UOM[0]})
    hass.states.async_set(entity_ids[1], VALUES[1], {ATTR_UNIT_OF_MEASUREMENT: UOM[1]})
    hass.states.async_set(entity_ids[2], VALUES[2], {ATTR_UNIT_OF_MEASUREMENT: UOM[2]})
    await hass.async_block_till_done()

    log = caplog.text

    assert "Units of measurement do not match for entity" in log


async def test_sensor_incorrect_values(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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

    state = hass.states.get("sensor.my_sum")
    assert state.state == "32.3"
    assert state.attributes.get(ATTR_ENTITIES) == [
        "sensor.test_1",
        "sensor.test_2",
        "sensor.test_3",
    ]
    assert state.attributes.get(ATTR_VALID_ENTITIES) == [
        "sensor.test_1",
        "sensor.test_3",
    ]
    assert state.attributes.get(ATTR_COUNT_VALID) == 2


async def test_sum_sensor_from_yaml_no_config(hass: HomeAssistant) -> None:
    """Test the sum sensor setup from integration yaml with missing config."""
    config = {
        "sensor": [
            {
                "platform": "sum",
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
                "unique_id": "very_unique_id",
                "name": "My Sum",
            }
        ]
    }

    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    entities = er.async_get(hass)
    assert entities.entities == {}
