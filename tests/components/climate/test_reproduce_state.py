"""The tests for reproduction of state."""

import pytest
from pytest_homeassistant.common import async_mock_service

from homeassistant.components.climate import (
    DOMAIN,
    ClimateEntityStateAttribute,
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.components.climate.reproduce_state import async_reproduce_states
from homeassistant.core import Context, HomeAssistant, State

ENTITY_1 = "climate.test1"
ENTITY_2 = "climate.test2"


@pytest.mark.parametrize("state", [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF])
async def test_with_hvac_mode(hass: HomeAssistant, state) -> None:
    """Test that state different hvac states."""
    calls = async_mock_service(hass, DOMAIN, ClimateService.SET_HVAC_MODE)

    await async_reproduce_states(hass, [State(ENTITY_1, state)])

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": ENTITY_1, "hvac_mode": state}


async def test_multiple_state(hass: HomeAssistant) -> None:
    """Test that multiple states gets calls."""
    calls_1 = async_mock_service(hass, DOMAIN, ClimateService.SET_HVAC_MODE)

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
    calls = async_mock_service(hass, DOMAIN, ClimateService.SET_HVAC_MODE)

    await async_reproduce_states(hass, [State(ENTITY_1, None)])

    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_state_with_context(hass: HomeAssistant) -> None:
    """Test that context is forwarded."""
    calls = async_mock_service(hass, DOMAIN, ClimateService.SET_HVAC_MODE)

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
        (ClimateService.SET_PRESET_MODE, ClimateEntityStateAttribute.PRESET_MODE),
        (ClimateService.SET_SWING_MODE, ClimateEntityStateAttribute.SWING_MODE),
        (
            ClimateService.SET_SWING_HORIZONTAL_MODE,
            ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE,
        ),
        (ClimateService.SET_FAN_MODE, ClimateEntityStateAttribute.FAN_MODE),
        (ClimateService.SET_HUMIDITY, ClimateEntityStateAttribute.TARGET_HUMIDITY),
        (
            ClimateService.SET_TEMPERATURE,
            ClimateEntityStateAttribute.TARGET_TEMPERATURE,
        ),
        (ClimateService.SET_TEMPERATURE, ClimateEntityStateAttribute.TARGET_TEMP_HIGH),
        (ClimateService.SET_TEMPERATURE, ClimateEntityStateAttribute.TARGET_TEMP_LOW),
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
        (ClimateService.SET_PRESET_MODE, ClimateEntityStateAttribute.PRESET_MODE),
        (ClimateService.SET_SWING_MODE, ClimateEntityStateAttribute.SWING_MODE),
        (
            ClimateService.SET_SWING_HORIZONTAL_MODE,
            ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE,
        ),
        (ClimateService.SET_FAN_MODE, ClimateEntityStateAttribute.FAN_MODE),
        (
            ClimateService.SET_TEMPERATURE,
            ClimateEntityStateAttribute.TARGET_TEMPERATURE,
        ),
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
    calls_1 = async_mock_service(hass, DOMAIN, ClimateService.SET_TEMPERATURE)

    await async_reproduce_states(
        hass,
        [
            State(
                ENTITY_1,
                None,
                {
                    ClimateEntityStateAttribute.TARGET_TEMPERATURE: 23.1,
                    ClimateEntityStateAttribute.TARGET_TEMP_HIGH: None,
                    ClimateEntityStateAttribute.TARGET_TEMP_LOW: None,
                },
            )
        ],
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {
        "entity_id": ENTITY_1,
        ClimateServiceArgument.TEMPERATURE: 23.1,
    }


async def test_attribute_partial_high_low_temperature(hass: HomeAssistant) -> None:
    """Test that service call ignores null attributes."""
    calls_1 = async_mock_service(hass, DOMAIN, ClimateService.SET_TEMPERATURE)

    await async_reproduce_states(
        hass,
        [
            State(
                ENTITY_1,
                None,
                {
                    ClimateEntityStateAttribute.TARGET_TEMPERATURE: None,
                    ClimateEntityStateAttribute.TARGET_TEMP_HIGH: 30.1,
                    ClimateEntityStateAttribute.TARGET_TEMP_LOW: 20.2,
                },
            )
        ],
    )

    await hass.async_block_till_done()

    assert len(calls_1) == 1
    assert calls_1[0].data == {
        "entity_id": ENTITY_1,
        ClimateServiceArgument.TARGET_TEMP_HIGH: 30.1,
        ClimateServiceArgument.TARGET_TEMP_LOW: 20.2,
    }
