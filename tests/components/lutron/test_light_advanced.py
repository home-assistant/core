"""Test advanced Lutron light features."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.light import (
    ATTR_FLASH,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_light_transition(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test light turn on/off with transition."""
    mock_config_entry.add_to_hass(hass)

    light = mock_lutron.areas[0].outputs[0]
    light.level = 0
    light.last_level.return_value = 0

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "light.test_light"

    # Turn on with transition
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: 2.5},
        blocking=True,
    )
    # Default brightness is used if not specified (DEFAULT_DIMMER_LEVEL is 50%)
    light.set_level.assert_called_with(
        new_level=pytest.approx(50.0, abs=0.5), fade_time_seconds=2.5
    )

    # Turn off with transition
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: 3.0},
        blocking=True,
    )
    light.set_level.assert_called_with(new_level=0, fade_time_seconds=3.0)


async def test_light_flash(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test light flash."""
    mock_config_entry.add_to_hass(hass)

    light = mock_lutron.areas[0].outputs[0]

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "light.test_light"

    # Short flash
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_FLASH: "short"},
        blocking=True,
    )
    light.flash.assert_called_with(0.5)

    # Long flash
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_FLASH: "long"},
        blocking=True,
    )
    light.flash.assert_called_with(1.5)


async def test_light_brightness_restore(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test light brightness restore logic."""
    mock_config_entry.add_to_hass(hass)

    light = mock_lutron.areas[0].outputs[0]
    light.level = 0
    light.last_level.return_value = 0

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "light.test_light"

    # Turn on first time - uses default (50%)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    light.set_level.assert_called_with(new_level=pytest.approx(50.0, abs=0.5))

    # Simulate update to 50% (Lutron level 50 -> HA level 127)
    light.last_level.return_value = 50
    callback = light.subscribe.call_args[0][0]
    callback(light, None, None, None)
    await hass.async_block_till_done()

    # Turn off
    light.last_level.return_value = 0
    callback(light, None, None, None)
    await hass.async_block_till_done()

    # Turn on again - should restore ~50%
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    # HA level 127 -> Lutron level ~49.8
    light.set_level.assert_called_with(new_level=pytest.approx(50.0, abs=0.5))
