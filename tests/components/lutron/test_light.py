"""Test Lutron light platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_light_setup(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test light setup."""
    mock_config_entry.add_to_hass(hass)

    # The mock_lutron already has one light from conftest
    light = mock_lutron.areas[0].outputs[0]
    light.level = 0
    light.last_level.return_value = 0

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light")
    assert state is not None
    assert state.state == STATE_OFF


async def test_light_turn_on_off(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test light turn on and off."""
    mock_config_entry.add_to_hass(hass)

    light = mock_lutron.areas[0].outputs[0]
    light.level = 0
    light.last_level.return_value = 0

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "light.test_light"

    # Turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    light.set_level.assert_called_with(new_level=pytest.approx(50.196, rel=1e-3))

    # Turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    light.set_level.assert_called_with(new_level=0)


async def test_light_update(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test light state update from library."""
    mock_config_entry.add_to_hass(hass)

    light = mock_lutron.areas[0].outputs[0]
    light.level = 0
    light.last_level.return_value = 0

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "light.test_light"
    assert hass.states.get(entity_id).state == STATE_OFF

    # Simulate update from library
    light.last_level.return_value = 100
    # The library calls the callback registered with subscribe
    callback = light.subscribe.call_args[0][0]
    callback(light, None, None, None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON
    assert hass.states.get(entity_id).attributes[ATTR_BRIGHTNESS] == 255
