"""The OpenRGB integration."""

from collections import defaultdict
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


def _build_hid_index_map(old_uids: list[str]) -> dict[str, str]:
    """Map old HID unique IDs to new indexed ones.

    Groups UIDs that share the same base key (first 5 parts), sorts each group
    by old location for deterministic ordering, and assigns indices 0, 1, 2, …

    Only UIDs with a 6-part format whose location starts with ``HID:`` are
    considered; all others are ignored.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for uid in old_uids:
        parts = uid.split(UID_SEPARATOR)
        if len(parts) == 6 and parts[5].startswith("HID:"):
            base_key = UID_SEPARATOR.join(parts[:5])
            groups[base_key].append(uid)

    mapping: dict[str, str] = {}
    for base_key, uids in groups.items():
        uids.sort(key=lambda u: u.split(UID_SEPARATOR)[5])
        for idx, uid in enumerate(uids):
            new_uid = f"{base_key}{UID_SEPARATOR}hid_{idx}"
            if uid != new_uid:
                mapping[uid] = new_uid
    return mapping


def _async_migrate_unique_ids(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> None:
    """Migrate entity and device unique IDs to the new indexed HID format.

    Old format: ...||HID: DevSrvsID:xxx  (raw location)
    New format: ...||hid_N              (indexed)
    """
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    # --- Entity migration ---
    entities = ent_reg.entities.get_entries_for_config_entry_id(entry.entry_id)
    ent_map = _build_hid_index_map([e.unique_id for e in entities])
    for entity in entities:
        if new_uid := ent_map.get(entity.unique_id):
            _LOGGER.debug(
                "Migrating entity unique ID from %s to %s",
                entity.unique_id,
                new_uid,
            )
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=new_uid)

    # --- Device migration ---
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    dev_ids = [
        identifier
        for device in devices
        for domain, identifier in device.identifiers
        if domain == DOMAIN
    ]
    dev_map = _build_hid_index_map(dev_ids)
    for device in devices:
        new_identifiers = {
            (d, dev_map.get(i, i)) if d == DOMAIN else (d, i)
            for d, i in device.identifiers
        }
        if new_identifiers != device.identifiers:
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
