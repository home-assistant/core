"""Test Homee switches."""

from unittest.mock import MagicMock

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry


async def test_switch_on(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn-on service."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_switch"},
        blocking=True,
    )

    assert mock_homee.set_value.assert_called_once_with(1, 11, 1)


async def test_switch_off(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn-off service."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch_identification_mode"},
        blocking=True,
    )

    assert mock_homee.set_value.assert_called_once_with(1, 4, 0)
