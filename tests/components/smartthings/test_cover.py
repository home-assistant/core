"""Test for the SmartThings cover platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import Attribute, Capability

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_entity_and_device_attributes(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "Garage", [Capability.garage_door_control], {Attribute.door: "open"}
    )
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Act
    await setup_platform(hass, COVER_DOMAIN, devices=[device])
    # Assert
    entry = entity_registry.async_get("cover.garage")
    assert entry
    assert entry.unique_id == device.device_id

    entry = device_registry.async_get_device({(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == device.device_type_name
    assert entry.manufacturer == "Unavailable"


async def test_open(hass: HomeAssistant, device_factory) -> None:
    """Test the cover opens doors, garages, and shades successfully."""
    # Arrange
    devices = {
        device_factory("Door", [Capability.door_control], {Attribute.door: "closed"}),
        device_factory(
            "Garage", [Capability.garage_door_control], {Attribute.door: "closed"}
        ),
        device_factory(
            "Shade", [Capability.window_shade], {Attribute.window_shade: "closed"}
        ),
    }
    await setup_platform(hass, COVER_DOMAIN, devices=devices)
    entity_ids = ["cover.door", "cover.garage", "cover.shade"]
    # Act
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_ids}, blocking=True
    )
    # Assert
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OPENING


async def test_close(hass: HomeAssistant, device_factory) -> None:
    """Test the cover closes doors, garages, and shades successfully."""
    # Arrange
    devices = {
        device_factory("Door", [Capability.door_control], {Attribute.door: "open"}),
        device_factory(
            "Garage", [Capability.garage_door_control], {Attribute.door: "open"}
        ),
        device_factory(
            "Shade", [Capability.window_shade], {Attribute.window_shade: "open"}
        ),
    }
    await setup_platform(hass, COVER_DOMAIN, devices=devices)
    entity_ids = ["cover.door", "cover.garage", "cover.shade"]
    # Act
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_ids}, blocking=True
    )
    # Assert
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_CLOSING


async def test_set_cover_position(hass: HomeAssistant, device_factory) -> None:
    """Test the cover sets to the specific position."""
    # Arrange
    device = device_factory(
        "Shade",
        [Capability.window_shade, Capability.battery, Capability.switch_level],
        {Attribute.window_shade: "opening", Attribute.battery: 95, Attribute.level: 10},
    )
    await setup_platform(hass, COVER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_POSITION: 50, "entity_id": "all"},
        blocking=True,
    )

    state = hass.states.get("cover.shade")
    # Result of call does not update state
    assert state.state == STATE_OPENING
    assert state.attributes[ATTR_BATTERY_LEVEL] == 95
    assert state.attributes[ATTR_CURRENT_POSITION] == 10
    # Ensure API called

    assert device._api.post_device_command.call_count == 1  # type: ignore


async def test_set_cover_position_unsupported(
    hass: HomeAssistant, device_factory
) -> None:
    """Test set position does nothing when not supported by device."""
    # Arrange
    device = device_factory(
        "Shade", [Capability.window_shade], {Attribute.window_shade: "opening"}
    )
    await setup_platform(hass, COVER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {"entity_id": "all", ATTR_POSITION: 50},
        blocking=True,
    )

    state = hass.states.get("cover.shade")
    assert ATTR_CURRENT_POSITION not in state.attributes

    # Ensure API was not called

    assert device._api.post_device_command.call_count == 0  # type: ignore


async def test_update_to_open_from_signal(hass: HomeAssistant, device_factory) -> None:
    """Test the cover updates to open when receiving a signal."""
    # Arrange
    device = device_factory(
        "Garage", [Capability.garage_door_control], {Attribute.door: "opening"}
    )
    await setup_platform(hass, COVER_DOMAIN, devices=[device])
    device.status.update_attribute_value(Attribute.door, "open")
    assert hass.states.get("cover.garage").state == STATE_OPENING
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("cover.garage")
    assert state is not None
    assert state.state == STATE_OPEN


async def test_update_to_closed_from_signal(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the cover updates to closed when receiving a signal."""
    # Arrange
    device = device_factory(
        "Garage", [Capability.garage_door_control], {Attribute.door: "closing"}
    )
    await setup_platform(hass, COVER_DOMAIN, devices=[device])
    device.status.update_attribute_value(Attribute.door, "closed")
    assert hass.states.get("cover.garage").state == STATE_CLOSING
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("cover.garage")
    assert state is not None
    assert state.state == STATE_CLOSED


async def test_unload_config_entry(hass: HomeAssistant, device_factory) -> None:
    """Test the lock is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory(
        "Garage", [Capability.garage_door_control], {Attribute.door: "open"}
    )
    config_entry = await setup_platform(hass, COVER_DOMAIN, devices=[device])
    config_entry.state = ConfigEntryState.LOADED
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, COVER_DOMAIN)
    # Assert
    assert hass.states.get("cover.garage").state == STATE_UNAVAILABLE
