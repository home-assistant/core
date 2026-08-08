"""The ZhongHong HVAC integration."""

from collections.abc import Iterable

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import (
    DeviceAddress,
    ZhongHongConfigEntry,
    ZhongHongCoordinator,
    device_unique_id,
    legacy_device_unique_id,
)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


@callback
def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: ZhongHongConfigEntry, addresses: Iterable[DeviceAddress]
) -> None:
    """Move the entities off the identifier the YAML platform gave them.

    That identifier was the address on the bus and nothing else, so a second
    gateway with an air conditioner at the same address produced an entity
    Home Assistant refused to add. Moving them keeps their entity IDs, and
    with those their recorded history.

    Only entities this entry owns are moved. An entity the YAML platform
    registered has no owner yet, and is claimed by whichever entry sets up
    first; there can only be one, since the old identifier is what stopped a
    second from ever being created.
    """
    entity_registry = er.async_get(hass)

    for address in addresses:
        entity_id = entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, legacy_device_unique_id(address)
        )
        if entity_id is None:
            continue

        registry_entry = entity_registry.async_get(entity_id)
        if registry_entry is None or registry_entry.config_entry_id not in (
            None,
            entry.entry_id,
        ):
            continue

        entity_registry.async_update_entity(
            entity_id, new_unique_id=device_unique_id(entry, address)
        )


async def async_setup_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Set up ZhongHong from a config entry."""
    coordinator = ZhongHongCoordinator(hass, entry)
    # Discovery and the listener thread are started from the coordinator's
    # _async_setup, so a failure here leaves nothing behind: the coordinator
    # registers its own shutdown against the entry.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    _async_migrate_unique_ids(hass, entry, coordinator.devices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
