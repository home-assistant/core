"""Tests for the Poolside body-of-water temperature sensor."""

from typing import Any

import pytest

from homeassistant.components.poolside.const import ControlType, GroupKind
from homeassistant.components.poolside.models import PoolsideControl
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import (
    TEST_BODY_OF_WATER_UUID,
    FakePoolsideClient,
    make_control,
    make_group,
)

ENTITY_ID = "sensor.pool_temperature"


@pytest.fixture
def controls(hass: HomeAssistant) -> list[PoolsideControl]:
    """Two controls sharing the pool group, plus one on a landscape group.

    Only the pool (a group with a BodyOfWaterUUID) should get a temperature
    sensor, and only one of it. Uses imperial units so the sensor's Fahrenheit
    native unit matches the test hass's unit system and needs no conversion.
    """
    hass.config.units = US_CUSTOMARY_SYSTEM
    landscape = make_group("group-yard", "Yard", kind=GroupKind.LANDSCAPE)
    return [
        make_control("heater-1", "Heater", ControlType.TEMPERATURE),
        make_control("light-1", "Pool Light", ControlType.LIGHT),
        make_control("light-2", "Yard Light", ControlType.LIGHT, group=landscape),
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_one_sensor_per_body_of_water(hass: HomeAssistant) -> None:
    """Only the pool gets a sensor: one per body of water, none for landscape groups."""
    assert hass.states.async_entity_ids("sensor") == [ENTITY_ID]


@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param(79, "79.0", id="numeric"),
        pytest.param("79", "79.0", id="stringly-typed"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_state_reflects_body_temperature_push(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    raw_value: Any,
    expected_state: str,
) -> None:
    """The sensor renders Temperature pushes keyed by the body of water's UUID."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(TEST_BODY_OF_WATER_UUID, "Temperature", raw_value)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("setup_integration")
async def test_unavailable_while_disconnected(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """The sensor mirrors the controller connection's availability."""
    fake_client.set_status(TEST_BODY_OF_WATER_UUID, "Temperature", 79)
    fake_client.set_connected(False)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    fake_client.set_connected(True)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "79.0"
