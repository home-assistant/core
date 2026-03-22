"""Support for EnOcean devices."""

from enocean_async import DEVICE_TYPES, EURID, Gateway
from enocean_async.address import BaseAddress

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    CONF_ENOCEAN_DEVICES,
    CONF_ENOCEAN_SENDER_ID,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)

type EnOceanConfigEntry = ConfigEntry[Gateway]

# ---------------------------------------------------------------------------
# Config entry migration
# ---------------------------------------------------------------------------

# Maps homeassistant_enocean v0.0.x unique_id strings to enocean_async DeviceType.id strings.
# Generic EEPs (e.g. "A5-02-01") are handled by the "EEP/" prefix rule below;
# only manufacturer-specific entries that changed naming need explicit entries here.
_DEVICE_TYPE_ID_V1_TO_V2: dict[str, str] = {
    "Eltako_FAH65s": "ELTAKO/FAH65S",
    "Eltako_FABH65S": "ELTAKO/FABH65S",
    "Eltako_FUD61NPN": "ELTAKO/FUD61NPN",
    "Eltako_FLD61": "ELTAKO/FLD61",
    "Eltako_FT55": "ELTAKO/FT55",
    "Jung_ENO": "JUNG/ENO",
    "Omnio_WS-CH-102": "OMNIO/WS-CH-102",
    "TRIO2SYS_WallSwitches": "TRIO_2_SYS/WALL-SWITCH",
    "NodOn_PIR-2-1-01": "NODON/PIR-2-1-01",
    "NodOn_SIN-2-1-01": "NODON/SIN-2-1-01",
    "NodOn_SIN-2-2-01": "NODON/SIN-2-2-01",
    "NodOn_SIN-2-RS-01": "NODON/SIN-2-RS-01",
    "Permundo_PSC234": "PERMUNDO/PSC234",
}


def _migrate_device_type_id(old_id: str) -> str | None:
    """Return the v2 DeviceType.id for a v1 device_type_id, or None if unmappable.

    Returns None when the old EEP has been removed from the new library and
    there is no suitable replacement; the caller should drop the device.
    """
    if old_id in _DEVICE_TYPE_ID_V1_TO_V2:
        new_id = _DEVICE_TYPE_ID_V1_TO_V2[old_id]
        return new_id if new_id in DEVICE_TYPES else None

    # Generic EEP strings like "A5-02-01" become "EEP/A5-02-01".
    candidate = f"EEP/{old_id}"
    return candidate if candidate in DEVICE_TYPES else None


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: EnOceanConfigEntry
) -> bool:
    """Migrate config entry to current version."""
    LOGGER.debug(
        "Migrating EnOcean config entry from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version == 1:
        devices: list[dict] = list(config_entry.options.get(CONF_ENOCEAN_DEVICES, []))
        migrated: list[dict] = []
        for device in devices:
            old_type_id: str = device.get(CONF_ENOCEAN_DEVICE_TYPE_ID, "")
            new_type_id = _migrate_device_type_id(old_type_id)
            if new_type_id is None:
                LOGGER.warning(
                    "EnOcean device type '%s' (device %s) is no longer supported "
                    "and will be removed from the configuration",
                    old_type_id,
                    device.get(CONF_ENOCEAN_DEVICE_ID, "unknown"),
                )
                continue
            migrated.append({**device, CONF_ENOCEAN_DEVICE_TYPE_ID: new_type_id})

        hass.config_entries.async_update_entry(
            config_entry,
            options={**config_entry.options, CONF_ENOCEAN_DEVICES: migrated},
            version=2,
            minor_version=1,
        )
        LOGGER.info(
            "Migrated EnOcean config entry to version 2.1 "
            "(%d device(s) kept, %d dropped)",
            len(migrated),
            len(devices) - len(migrated),
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
) -> bool:
    """Set up an EnOcean gateway for the given config entry."""
    gateway = Gateway(config_entry.data[CONF_DEVICE])

    try:
        await gateway.start()
    except ConnectionError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to EnOcean gateway: {err}"
        ) from err

    config_entry.runtime_data = gateway
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    async_cleanup_device_registry(hass=hass, entry=config_entry)

    version_info = gateway.version_info
    if version_info is None:
        raise ConfigEntryNotReady("EnOcean gateway did not respond to version query")

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, str(version_info.eurid))},
        manufacturer="EnOcean",
        name="EnOcean Gateway",
        model=version_info.app_description,
        serial_number=str(version_info.eurid),
        sw_version=version_info.app_version.version_string,
    )

    # Add devices to the gateway so it can decode their telegrams.
    base_id = gateway.base_id
    for device in config_entry.options.get(CONF_ENOCEAN_DEVICES, []):
        try:
            enocean_id = EURID(device[CONF_ENOCEAN_DEVICE_ID])
            device_type = DEVICE_TYPES[device[CONF_ENOCEAN_DEVICE_TYPE_ID]]
            sender_id_string: str | None = device.get(CONF_ENOCEAN_SENDER_ID)
            sender = BaseAddress(sender_id_string) if sender_id_string else base_id
            gateway.add_device(
                address=enocean_id,
                device_type=device_type,
                sender=sender,
            )
        except (KeyError, ValueError) as ex:
            LOGGER.error(
                "Failed to add EnOcean device %s: %s",
                device.get(CONF_ENOCEAN_DEVICE_ID, "unknown"),
                ex,
            )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


@callback
def async_cleanup_device_registry(
    hass: HomeAssistant,
    entry: EnOceanConfigEntry,
) -> None:
    """Remove entries from device registry if device is removed."""
    device_registry = dr.async_get(hass)
    hass_devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=entry.entry_id,
    )

    device_ids = [
        dev["id"].upper() for dev in entry.options.get(CONF_ENOCEAN_DEVICES, [])
    ]

    for hass_device in hass_devices:
        for item in hass_device.identifiers:
            domain = item[0]
            device_id = (str(item[1]).split("-", maxsplit=1)[0]).upper()
            if domain == DOMAIN and device_id not in device_ids:
                LOGGER.debug(
                    "Removing Home Assistant device %s and associated entities for unconfigured EnOcean device %s",
                    hass_device.id,
                    device_id,
                )
                device_registry.async_update_device(
                    hass_device.id, remove_config_entry_id=entry.entry_id
                )
                break


async def async_reload_entry(hass: HomeAssistant, entry: EnOceanConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EnOceanConfigEntry) -> bool:
    """Unload EnOcean config entry."""
    if unload_platforms := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        entry.runtime_data.stop()

    return unload_platforms
