"""Test Lutron light platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_FLASH,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def setup_platforms():
    """Patch PLATFORMS for all tests in this file."""
    with patch("homeassistant.components.lutron.PLATFORMS", [Platform.LIGHT]):
        yield


async def test_light_setup(
    hass: HomeAssistant,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test light setup."""
    mock_config_entry.add_to_hass(hass)

    light = mock_lutron.areas[0].outputs[0]
    light.level = 0
    light.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_light_turn_on_off(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test light turn on and off."""
    mock_config_entry.add_to_hass(hass)

    light = mock_lutron.areas[0].outputs[0]
    light.level = 0
    light.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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


async def test_light_transition(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test light turn on/off with transition."""
    mock_config_entry.add_to_hass(hass)

    light = mock_lutron.areas[0].outputs[0]
    light.level = 0
    light.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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
