"""Tests for JVC Projector select platform."""

from unittest.mock import MagicMock, patch

from jvcprojector import const

from homeassistant.components.jvc_projector.select import OPTIONS
from homeassistant.components.select import (
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_all_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all selects are created correctly."""
    with patch("homeassistant.components.jvc_projector.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    # Test each defined select entity
    for cmd_key, expected_options in OPTIONS.items():
        entity_id = f"select.jvc_projector_{cmd_key}"
        entity = hass.states.get(entity_id)
        assert entity, f"Entity {entity_id} was not created"

        # Verify the entity's options
        assert entity.attributes.get(ATTR_OPTIONS) == expected_options

        # Verify the current state matches what's in the mock device
        expected_state = mock_device.get_state.return_value.get(cmd_key)
        if expected_state:
            assert entity.state == expected_state


async def test_select_option(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting an option for each select."""
    with patch("homeassistant.components.jvc_projector.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    # Test each select's option selection
    test_cases = [
        ("input", const.HDMI2),
        ("eshift", const.OFF),
        ("laser_power", const.HIGH),
        ("installation_mode", "mode2"),
        ("anamorphic", const.ANAMORPHIC_A),
        ("laser_dimming", const.AUTO1),
    ]

    for cmd_key, test_value in test_cases:
        entity_id = f"select.jvc_projector_{cmd_key}"

        # Call the service to change the option
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: test_value,
            },
            blocking=True,
        )

        # Verify the command was sent
        mock_device.send_command.assert_any_call(cmd_key, test_value)

        # Reset the mock for the next test
        mock_device.send_command.reset_mock()
