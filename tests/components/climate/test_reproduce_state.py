"""The tests for reproduction of state."""

import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate.reproduce_state import async_reproduce_states
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import Context, HomeAssistant, State

from tests.common import async_mock_service

ENTITY_1 = "climate.test1"
ENTITY_2 = "climate.test2"


@pytest.mark.parametrize("state", [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF])
async def test_with_hvac_mode(hass: HomeAssistant, state) -> None:
    """Test that state different hvac states."""
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HVAC_MODE)

    await async_reproduce_states(hass, [State(ENTITY_1, state)])

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": ENTITY_1, "hvac_mode": state}


async def test_multiple_state(hass: HomeAssistant) -> None:
    """Test that multiple states gets calls."""
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_SET_HVAC_MODE)

    await async_reproduce_states(
        hass, [State(ENTITY_1, HVACMode.HEAT), State(ENTITY_2, HVACMode.AUTO)]
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 2
    # order is not guaranteed
    assert any(
        call.data == {"entity_id": ENTITY_1, "hvac_mode": HVACMode.HEAT}
        for call in calls_1
    )
    assert any(
        call.data == {"entity_id": ENTITY_2, "hvac_mode": HVACMode.AUTO}
        for call in calls_1
    )


async def test_state_with_none(hass: HomeAssistant) -> None:
    """Test that none is not a hvac state."""
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HVAC_MODE)

    await async_reproduce_states(hass, [State(ENTITY_1, None)])

    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_state_with_context(hass: HomeAssistant) -> None:
    """Test that context is forwarded."""
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HVAC_MODE)

    context = Context()

    await async_reproduce_states(
        hass, [State(ENTITY_1, HVACMode.HEAT)], context=context
    )

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": ENTITY_1, "hvac_mode": HVACMode.HEAT}
    assert calls[0].context == context


@pytest.mark.parametrize(
    ("service", "attribute"),
    [
        (SERVICE_SET_PRESET_MODE, ATTR_PRESET_MODE),
        (SERVICE_SET_SWING_MODE, ATTR_SWING_MODE),
        (SERVICE_SET_SWING_HORIZONTAL_MODE, ATTR_SWING_HORIZONTAL_MODE),
        (SERVICE_SET_FAN_MODE, ATTR_FAN_MODE),
        (SERVICE_SET_HUMIDITY, ATTR_HUMIDITY),
        (SERVICE_SET_TEMPERATURE, ATTR_TEMPERATURE),
        (SERVICE_SET_TEMPERATURE, ATTR_TARGET_TEMP_HIGH),
        (SERVICE_SET_TEMPERATURE, ATTR_TARGET_TEMP_LOW),
    ],
)
async def test_attribute(hass: HomeAssistant, service, attribute) -> None:
    """Test that service call is made for each attribute."""
    calls_1 = async_mock_service(hass, DOMAIN, service)

    value = "dummy"

    await async_reproduce_states(hass, [State(ENTITY_1, None, {attribute: value})])

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {"entity_id": ENTITY_1, attribute: value}


@pytest.mark.parametrize(
    ("service", "attribute"),
    [
        (SERVICE_SET_PRESET_MODE, ATTR_PRESET_MODE),
        (SERVICE_SET_SWING_MODE, ATTR_SWING_MODE),
        (SERVICE_SET_SWING_HORIZONTAL_MODE, ATTR_SWING_HORIZONTAL_MODE),
        (SERVICE_SET_FAN_MODE, ATTR_FAN_MODE),
    ],
)
async def test_attribute_with_none(hass: HomeAssistant, service, attribute) -> None:
    """Test that service call is not made for attributes with None value."""
    calls_1 = async_mock_service(hass, DOMAIN, service)

    await async_reproduce_states(hass, [State(ENTITY_1, None, {attribute: None})])

    await hass.async_block_till_done()

    assert len(calls_1) == 0


async def test_attribute_partial_temperature(hass: HomeAssistant) -> None:
    """Test that service call ignores null attributes."""
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_SET_TEMPERATURE)

    await async_reproduce_states(
        hass,
        [
            State(
                ENTITY_1,
                None,
                {
                    ATTR_TEMPERATURE: 23.1,
                    ATTR_TARGET_TEMP_HIGH: None,
                    ATTR_TARGET_TEMP_LOW: None,
                },
            )
        ],
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {"entity_id": ENTITY_1, ATTR_TEMPERATURE: 23.1}


async def test_attribute_partial_high_low_temperature(hass: HomeAssistant) -> None:
    """Test that service call ignores null attributes."""
    calls_1 = async_mock_service(hass, DOMAIN, SERVICE_SET_TEMPERATURE)

    await async_reproduce_states(
        hass,
        [
            State(
                ENTITY_1,
                None,
                {
                    ATTR_TEMPERATURE: None,
                    ATTR_TARGET_TEMP_HIGH: 30.1,
                    ATTR_TARGET_TEMP_LOW: 20.2,
                },
            )
        ],
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {
        "entity_id": ENTITY_1,
        ATTR_TARGET_TEMP_HIGH: 30.1,
        ATTR_TARGET_TEMP_LOW: 20.2,
    }
