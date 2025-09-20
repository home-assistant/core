"""Test the Zimi fan entity."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import FanEntityFeature
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ENTITY_INFO, mock_api_device, setup_platform


async def test_fan_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests fan entity."""

    device_name = "Fan Controller"
    entity_key = "fan.fan_controller_test_entity_name"
    entity_type = Platform.FAN

    mock_api.fans = [mock_api_device(device_name=device_name, entity_type=entity_type)]

    await setup_platform(hass, entity_type)

    entity = entity_registry.entities[entity_key]
    assert entity.unique_id == ENTITY_INFO["id"]

    assert (
        entity.supported_features
        == FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    state = hass.states.get(entity_key)
    assert state == snapshot

    services = hass.services.async_services()

    assert SERVICE_TURN_ON in services[entity_type]

    await hass.services.async_call(
        entity_type,
        SERVICE_TURN_ON,
        {"entity_id": entity_key},
        blocking=True,
    )

    assert mock_api.fans[0].turn_on.called

    assert SERVICE_TURN_OFF in services[entity_type]

    await hass.services.async_call(
        entity_type,
        SERVICE_TURN_OFF,
        {"entity_id": entity_key},
        blocking=True,
    )

    assert mock_api.fans[0].turn_off.called

    assert "set_percentage" in services[entity_type]
    await hass.services.async_call(
        entity_type,
        "set_percentage",
        {"entity_id": entity_key, "percentage": 50},
        blocking=True,
    )
    assert mock_api.fans[0].set_fanspeed.called
