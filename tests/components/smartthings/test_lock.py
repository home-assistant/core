"""
Test for the SmartThings lock platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import Attribute, Capability
from pysmartthings.device import Status

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_entity_and_device_attributes(hass, device_factory):
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory("Lock_1", [Capability.lock], {Attribute.lock: "unlocked"})
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    device_registry = await hass.helpers.device_registry.async_get_registry()
    # Act
    await setup_platform(hass, LOCK_DOMAIN, devices=[device])
    # Assert
    entry = entity_registry.async_get("lock.lock_1")
    assert entry
    assert entry.unique_id == device.device_id

    entry = device_registry.async_get_device({(DOMAIN, device.device_id)})
    assert entry
    assert entry.name == device.label
    assert entry.model == device.device_type_name
    assert entry.manufacturer == "Unavailable"


async def test_lock(hass, device_factory):
    """Test the lock locks successfully."""
    # Arrange
    device = device_factory("Lock_1", [Capability.lock])
    device.status.attributes[Attribute.lock] = Status(
        "unlocked",
        None,
        {
            "method": "Manual",
            "codeId": None,
            "codeName": "Code 1",
            "lockName": "Front Door",
            "usedCode": "Code 2",
        },
    )
    await setup_platform(hass, LOCK_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        LOCK_DOMAIN, "lock", {"entity_id": "lock.lock_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("lock.lock_1")
    assert state is not None
    assert state.state == "locked"
    assert state.attributes["method"] == "Manual"
    assert state.attributes["lock_state"] == "locked"
    assert state.attributes["code_name"] == "Code 1"
    assert state.attributes["used_code"] == "Code 2"
    assert state.attributes["lock_name"] == "Front Door"
    assert "code_id" not in state.attributes


async def test_unlock(hass, device_factory):
    """Test the lock unlocks successfully."""
    # Arrange
    device = device_factory("Lock_1", [Capability.lock], {Attribute.lock: "locked"})
    await setup_platform(hass, LOCK_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        LOCK_DOMAIN, "unlock", {"entity_id": "lock.lock_1"}, blocking=True
    )
    # Assert
    state = hass.states.get("lock.lock_1")
    assert state is not None
    assert state.state == "unlocked"


async def test_update_from_signal(hass, device_factory):
    """Test the lock updates when receiving a signal."""
    # Arrange
    device = device_factory("Lock_1", [Capability.lock], {Attribute.lock: "unlocked"})
    await setup_platform(hass, LOCK_DOMAIN, devices=[device])
    await device.lock(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("lock.lock_1")
    assert state is not None
    assert state.state == "locked"


async def test_unload_config_entry(hass, device_factory):
    """Test the lock is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory("Lock_1", [Capability.lock], {Attribute.lock: "locked"})
    config_entry = await setup_platform(hass, LOCK_DOMAIN, devices=[device])
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "lock")
    # Assert
    assert not hass.states.get("lock.lock_1")
