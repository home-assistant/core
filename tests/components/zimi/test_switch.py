"""Test the Zimi switch entity."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import DEVICE_INFO, ENTITY_INFO, mock_api_device, setup_platform
from .conftest import INPUT_MAC


async def test_switch_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests switch entity."""

    device_name = "Switch Controller"
    entity_key = "switch.test_entity_room_switch_controller_test_entity_name"
    entity_type = "switch"

    mock_api.outlets = [
        mock_api_device(device_name=device_name, entity_type=entity_type)
    ]

    await setup_platform(hass, Platform.SWITCH)

    entity = entity_registry.entities[entity_key]
    assert entity.unique_id == ENTITY_INFO["id"]

    state = hass.states.get(entity_key)
    assert state == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_key},
        blocking=True,
    )

    assert mock_api.outlets[0].turn_on.called

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_key},
        blocking=True,
    )

    assert mock_api.outlets[0].turn_off.called


async def test_switch_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_api: MagicMock,
) -> None:
    """Tests switch device is linked to the controller device via via_device_id."""

    mock_api.outlets = [mock_api_device(entity_type="switch")]

    config_entry = await setup_platform(hass, Platform.SWITCH)

    controller_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, INPUT_MAC), config_entry.entry_id
    )
    assert controller_device is not None

    switch_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_INFO["id"]), config_entry.entry_id
    )
    assert switch_device is not None
    assert switch_device.via_device_id == controller_device.id
