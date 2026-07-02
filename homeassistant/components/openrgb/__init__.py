"""The OpenRGB integration."""

from collections import defaultdict

from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, UID_SEPARATOR
from .coordinator import OpenRGBConfigEntry, OpenRGBCoordinator

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


def _build_hid_index_map(uids: list[str]) -> dict[str, str]:
    """Map old HID unique IDs to new indexed format.

    Groups UIDs sharing the same base key (first 5 parts), sorts each group
    by the old location for deterministic ordering, and assigns ``hid_0``,
    ``hid_1``, … suffixes.  UIDs that are not 6-part HID entries are ignored.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for uid in uids:
        parts = uid.split(UID_SEPARATOR)
        if len(parts) == 6 and parts[5].startswith("HID:"):
            groups[UID_SEPARATOR.join(parts[:5])].append(uid)

    mapping: dict[str, str] = {}
    for base_key, group in groups.items():
        group.sort(key=lambda u: u.split(UID_SEPARATOR)[5])
        for idx, uid in enumerate(group):
            new_uid = f"{base_key}{UID_SEPARATOR}hid_{idx}"
            if uid != new_uid:
                mapping[uid] = new_uid
    return mapping


def _async_migrate_unique_ids(hass: HomeAssistant, entry: OpenRGBConfigEntry) -> None:
    """Migrate entity and device unique IDs from raw HID locations to indexed format.

    Old format: ``…||HID: DevSrvsID:xxx``  New format: ``…||hid_N``
    """
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    entities = ent_reg.entities.get_entries_for_config_entry_id(entry.entry_id)
    ent_map = _build_hid_index_map([e.unique_id for e in entities])
    for entity in entities:
        if new_uid := ent_map.get(entity.unique_id):
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=new_uid)

    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    dev_map = _build_hid_index_map(
        [i for d in devices for dom, i in d.identifiers if dom == DOMAIN]
    )
    for device in devices:
        new_ids = {
            (dom, dev_map.get(i, i)) if dom == DOMAIN else (dom, i)
            for dom, i in device.identifiers
        }
        if new_ids != device.identifiers:
            dev_reg.async_update_device(device.id, new_identifiers=new_ids)


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
