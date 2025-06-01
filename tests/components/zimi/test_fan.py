"""Test the Zimi fan entity."""

from unittest.mock import MagicMock

from homeassistant.components.fan import FanEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ENTITY_INFO, check_states, check_toggle, mock_entity, setup_platform


async def test_fan_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_api: MagicMock
) -> None:
    """Tests fan entity."""

    device_name = "Fan Controller"
    entity_key = "fan.fan_controller_test_entity_name"
    entity_type = Platform.FAN

    mock_api.fans = [mock_entity(device_name=device_name, entity_type=entity_type)]

    await setup_platform(hass, entity_type)

    entity = entity_registry.entities[entity_key]
    assert entity.unique_id == ENTITY_INFO["id"]

    assert (
        entity.supported_features
        == FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    await check_states(hass, entity_type, entity_key)
    await check_toggle(
        hass,
        entity_type,
        entity_key,
        mock_api.fans[0],
    )

    services = hass.services.async_services()
    assert "set_percentage" in services[entity_type]
    await hass.services.async_call(
        entity_type,
        "set_percentage",
        {"entity_id": entity_key, "percentage": 50},
        blocking=True,
    )
    assert mock_api.fans[0].set_fanspeed.called
