"""Registry cleanup for live changes and devices removed while offline."""

from dataclasses import replace
from unittest.mock import patch

from lorawan_connection import EventType

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import RegisterBackend
from .helpers import DESCRIPTOR, inventory

from tests.common import MockConfigEntry


async def test_registry_lifecycle(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    registered_backend: RegisterBackend,
) -> None:
    """Delete registry entries on removal, but preserve them during an unload."""
    domain = "test_vendor"
    descriptor = DESCRIPTOR
    entry = MockConfigEntry(domain=domain)
    entry.add_to_hass(hass)
    connection, _unregister = await registered_backend("network", [descriptor])
    stale = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(domain, "network:0000000000000001")},
    )
    stale_entity = entity_registry.async_get_or_create(
        "sensor",
        domain,
        "stale",
        config_entry=entry,
        device_id=stale.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    with patch(
        "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert device_registry.async_get(stale.id) is None
        assert entity_registry.async_get(stale_entity.entity_id) is None
        device = device_registry.async_get_device_by_identifier(
            (domain, f"network:{descriptor.dev_eui}"), entry.entry_id
        )
        assert device is not None
        connection.emit(
            inventory(replace(descriptor, name="Renamed"), EventType.UPDATED)
        )
        assert device_registry.async_get(device.id).name == "Renamed"
        # Unload is not a device deletion.
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert device_registry.async_get(device.id) is not None
        # The device disappeared while HA was offline.
        connection.emit(inventory(descriptor, EventType.REMOVED))
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert device_registry.async_get(device.id) is None
        assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        connection.emit(inventory(descriptor))
        await hass.async_block_till_done()
        device = device_registry.async_get_device_by_identifier(
            (domain, f"network:{descriptor.dev_eui}"), entry.entry_id
        )
        assert device is not None
        # A profile change to an unsupported model removes all its entities too.
        connection.emit(
            inventory(replace(descriptor, model_id="unsupported"), EventType.UPDATED)
        )
        await hass.async_block_till_done()
        assert device_registry.async_get(device.id) is None
        assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        assert await hass.config_entries.async_unload(entry.entry_id)
