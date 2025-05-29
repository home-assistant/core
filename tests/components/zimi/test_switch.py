"""Test the Zimi switch entity."""

from unittest.mock import MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ENTITY_INFO, mock_entity, setup_platform


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
    state = hass.states.get(entity_key)
    assert state is not None
    assert state.state == "on"

    services = hass.services.async_services()
    assert "switch" in services
    assert "turn_on" in services["switch"]
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.outlets[0].turn_on.called

    assert "turn_off" in services["switch"]
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.outlets[0].turn_off.called
