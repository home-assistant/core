"""Test Lutron scene platform."""

from unittest.mock import MagicMock

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_scene_setup(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test scene setup."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    # The scene entity name is derived from the keypad and button
    # In conftest, we have keypad="Test Keypad", button="Test Button"
    state = hass.states.get("scene.test_keypad_test_button")
    assert state is not None


async def test_scene_activate(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test scene activation."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "scene.test_keypad_test_button"
    button = mock_lutron.areas[0].keypads[0].buttons[0]

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    button.tap.assert_called_once()
