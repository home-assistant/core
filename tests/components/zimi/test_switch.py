"""Test the Zimi switch entity."""

from unittest.mock import MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ENTITY_INFO, check_states, check_toggle, mock_entity, setup_platform


async def test_switch_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_api: MagicMock
) -> None:
    """Tests switch entity."""

    device_name = "Switch Controller"
    entity_key = "switch.switch_controller_test_entity_name"
    entity_type = "switch"

    mock_api.outlets = [mock_entity(device_name=device_name, entity_type=entity_type)]

    await setup_platform(hass, Platform.SWITCH)

    entity = entity_registry.entities[entity_key]
    assert entity.unique_id == ENTITY_INFO["id"]

    await check_states(hass, entity_type, entity_key)
    await check_toggle(hass, entity_type, entity_key, mock_api.outlets[0])
