"""The OpenRGB integration."""

import logging

from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, UID_SEPARATOR
from .coordinator import OpenRGBConfigEntry, OpenRGBCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SELECT]


def _setup_server_device_registry(
    hass: HomeAssistant, entry: OpenRGBConfigEntry, coordinator: OpenRGBCoordinator
):
    """Set up device registry for the OpenRGB SDK server."""
    device_registry = dr.async_get(hass)

    # Create the parent OpenRGB SDK server device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data[CONF_NAME],
        model="OpenRGB SDK Server",
        manufacturer="OpenRGB",
        sw_version=coordinator.get_client_protocol_version(),
        entry_type=dr.DeviceEntryType.SERVICE,
    )


async def async_setup_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Set up OpenRGB from a config entry."""
    _async_migrate_unique_ids(hass, entry)

    coordinator = OpenRGBCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    # The server device must be created first as other devices are children of it
    _setup_server_device_registry(hass, entry, coordinator)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _migrate_uid(unique_id: str) -> str | None:
    """Migrate an old-format unique ID to the new format.

    Old format included raw location for all devices. New format drops location
    for HID devices and for devices that have a serial number.

    Returns the new unique ID, or None if no migration is needed.
    """
    parts = unique_id.split(UID_SEPARATOR)
    if len(parts) != 6:
        return None

    serial = parts[4]
    location = parts[5]

    if location == "none":
        return None

    if location.startswith("HID:") or serial != "none":
        parts[5] = "none"
        return UID_SEPARATOR.join(parts)

    return None


def _async_migrate_unique_ids(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> None:
    """Migrate entity and device unique IDs to the new format."""
    # Migrate entity unique IDs
    ent_reg = er.async_get(hass)
    for entity in ent_reg.entities.get_entries_for_config_entry_id(entry.entry_id):
        if new_uid := _migrate_uid(entity.unique_id):
            _LOGGER.debug(
                "Migrating entity unique ID from %s to %s",
                entity.unique_id,
                new_uid,
            )
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=new_uid)

    # Migrate device identifiers
    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        new_identifiers: set[tuple[str, str]] = set()
        changed = False
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and (new_uid := _migrate_uid(identifier)):
                new_identifiers.add((domain, new_uid))
                changed = True
            else:
                new_identifiers.add((domain, identifier))
        if changed:
            _LOGGER.debug(
                "Migrating device identifiers from %s to %s",
                device.identifiers,
                new_identifiers,
            )
            dev_reg.async_update_device(device.id, new_identifiers=new_identifiers)


async def async_unload_entry(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: OpenRGBConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allows removal of device if it is no longer connected."""
    coordinator = entry.runtime_data

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue

        # Block removal of the OpenRGB SDK Server device
        if identifier == entry.entry_id:
            return False

        # Block removal of the OpenRGB device if it is still connected
        if identifier in coordinator.data:
            return False

    # Device is not connected or is not an OpenRGB device, allow removal
    return True
