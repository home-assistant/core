"""Test the Zimi light entity."""

from unittest.mock import MagicMock

from homeassistant.components.light import ColorMode
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ENTITY_INFO, mock_entity, setup_platform


async def test_light_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_api: MagicMock
) -> None:
    """Tests lights entity."""

    device_name = "Light Controller"
    entity_key = "light.light_controller_test_entity_name"
    entity_type = "light"

    mock_api.lights = [mock_entity(device_name=device_name, entity_type=entity_type)]

    await setup_platform(hass, Platform.LIGHT)

    entity = entity_registry.entities[entity_key]
    assert entity.unique_id == ENTITY_INFO["id"]
    assert entity.capabilities == {
        "supported_color_modes": [ColorMode.ONOFF],
    }
    state = hass.states.get(entity_key)
    assert state is not None
    assert state.state == "on"

    services = hass.services.async_services()
    assert "light" in services
    assert "turn_on" in services["light"]
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.lights[0].turn_on.called

    assert "turn_off" in services["light"]
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.lights[0].turn_off.called


async def test_dimmer_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_api: MagicMock
) -> None:
    """Tests dimmer entity."""

    device_name = "Light Controller"
    entity_key = "light.light_controller_test_entity_name"
    entity_type = "dimmer"

    mock_api.lights = [mock_entity(device_name=device_name, entity_type=entity_type)]

    await setup_platform(hass, Platform.LIGHT)

    entity = entity_registry.entities[entity_key]
    assert entity.unique_id == ENTITY_INFO["id"]
    assert entity.capabilities == {
        "supported_color_modes": [ColorMode.BRIGHTNESS],
    }
    state = hass.states.get(entity_key)
    assert state is not None
    assert state.state == "on"

    services = hass.services.async_services()
    assert "light" in services
    assert "turn_on" in services["light"]
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.lights[0].set_brightness.called

    assert "turn_off" in services["light"]
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.lights[0].set_brightness.called
