"""The tests for reproduction of state."""

import pytest

from homeassistant.components.climate.const import (
    ATTR_AUX_HEAT,
    ATTR_HUMIDITY,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SERVICE_SET_AUX_HEAT,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.reproduce_state import async_reproduce_states
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import Context, State

from tests.common import async_mock_service

ENTITY_1 = "climate.test1"
ENTITY_2 = "climate.test2"


@pytest.mark.parametrize("state", [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF])
async def test_with_hvac_mode(hass, state):
    """Test that state different hvac states."""
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HVAC_MODE)

    await async_reproduce_states(hass, [State(ENTITY_1, state)])

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": ENTITY_1, "hvac_mode": state}


async def test_multiple_state(hass):
    """Test that multiple states gets calls."""
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_SET_HVAC_MODE)

    await async_reproduce_states(
        hass, [State(ENTITY_1, HVAC_MODE_HEAT), State(ENTITY_2, HVAC_MODE_AUTO)]
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 2
    # order is not guaranteed
    assert any(
        call.data == {"entity_id": ENTITY_1, "hvac_mode": HVAC_MODE_HEAT}
        for call in calls_1
    )
    assert any(
        call.data == {"entity_id": ENTITY_2, "hvac_mode": HVAC_MODE_AUTO}
        for call in calls_1
    )


async def test_state_with_none(hass):
    """Test that none is not a hvac state."""
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HVAC_MODE)

    await async_reproduce_states(hass, [State(ENTITY_1, None)])

    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_state_with_context(hass):
    """Test that context is forwarded."""
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HVAC_MODE)

    context = Context()

    await async_reproduce_states(
        hass, [State(ENTITY_1, HVAC_MODE_HEAT)], context=context
    )

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": ENTITY_1, "hvac_mode": HVAC_MODE_HEAT}
    assert calls[0].context == context


@pytest.mark.parametrize(
    "service,attribute",
    [
        (SERVICE_SET_AUX_HEAT, ATTR_AUX_HEAT),
        (SERVICE_SET_PRESET_MODE, ATTR_PRESET_MODE),
        (SERVICE_SET_SWING_MODE, ATTR_SWING_MODE),
        (SERVICE_SET_HUMIDITY, ATTR_HUMIDITY),
        (SERVICE_SET_TEMPERATURE, ATTR_TEMPERATURE),
        (SERVICE_SET_TEMPERATURE, ATTR_TARGET_TEMP_HIGH),
        (SERVICE_SET_TEMPERATURE, ATTR_TARGET_TEMP_LOW),
    ],
)
async def test_attribute(hass, service, attribute):
    """Test that service call is made for each attribute."""
    calls_1 = async_mock_service(hass, DOMAIN, service)

    value = "dummy"

    await async_reproduce_states(hass, [State(ENTITY_1, None, {attribute: value})])

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {"entity_id": ENTITY_1, attribute: value}
