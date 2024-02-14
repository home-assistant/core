"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from pyrainbird.async_client import AsyncRainbirdClient, AsyncRainbirdController
from pyrainbird.exceptions import RainbirdApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_SERIAL_NUMBER
from .coordinator import RainbirdData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


DOMAIN = "rainbird"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the config entry for Rain Bird."""

    hass.data.setdefault(DOMAIN, {})

    controller = AsyncRainbirdController(
        AsyncRainbirdClient(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            entry.data[CONF_PASSWORD],
        )
    )

    if not (await _async_fix_unique_id(hass, controller, entry)):
        return False
    if mac_address := entry.data.get(CONF_MAC):
        _async_fix_entity_unique_id(
            hass,
            er.async_get(hass),
            entry.entry_id,
            format_mac(mac_address),
            str(entry.data[CONF_SERIAL_NUMBER]),
        )
        _async_fix_device_id(
            hass,
            dr.async_get(hass),
            entry.entry_id,
            format_mac(mac_address),
            str(entry.data[CONF_SERIAL_NUMBER]),
        )

    try:
        model_info = await controller.get_model_and_version()
    except RainbirdApiException as err:
        raise ConfigEntryNotReady from err

    data = RainbirdData(hass, entry, controller, model_info)
    await data.coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_fix_unique_id(
    hass: HomeAssistant, controller: AsyncRainbirdController, entry: ConfigEntry
) -> bool:
    """Update the config entry with a unique id based on the mac address."""
    _LOGGER.debug("Checking for migration of config entry (%s)", entry.unique_id)
    if not (mac_address := entry.data.get(CONF_MAC)):
        try:
            wifi_params = await controller.get_wifi_params()
        except RainbirdApiException as err:
            _LOGGER.warning("Unable to fix missing unique id: %s", err)
            return True

        if (mac_address := wifi_params.mac_address) is None:
            _LOGGER.warning("Unable to fix missing unique id (mac address was None)")
            return True

    new_unique_id = format_mac(mac_address)
    if entry.unique_id == new_unique_id and CONF_MAC in entry.data:
        _LOGGER.debug("Config entry already in correct state")
        return True

    entries = hass.config_entries.async_entries(DOMAIN)
    for existing_entry in entries:
        if existing_entry.unique_id == new_unique_id:
            _LOGGER.warning(
                "Unable to fix missing unique id (already exists); Removing duplicate entry"
            )
            hass.async_create_background_task(
                hass.config_entries.async_remove(entry.entry_id),
                "Remove rainbird config entry",
            )
            return False

    _LOGGER.debug("Updating unique id to %s", new_unique_id)
    hass.config_entries.async_update_entry(
        entry,
        unique_id=new_unique_id,
        data={
            **entry.data,
            CONF_MAC: mac_address,
        },
    )
    return True


def _async_fix_entity_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_id: str,
    mac_address: str,
    serial_number: str,
) -> None:
    """Migrate existing entity if current one can't be found and an old one exists."""
    entity_entries = er.async_entries_for_config_entry(entity_registry, config_entry_id)
    for entity_entry in entity_entries:
        unique_id = str(entity_entry.unique_id)
        if unique_id.startswith(mac_address):
            continue
        if (suffix := unique_id.removeprefix(str(serial_number))) != unique_id:
            new_unique_id = f"{mac_address}{suffix}"
            _LOGGER.debug("Updating unique id from %s to %s", unique_id, new_unique_id)
            entity_registry.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_unique_id
            )


def _async_device_entry_to_keep(
    old_entry: dr.DeviceEntry, new_entry: dr.DeviceEntry
) -> dr.DeviceEntry:
    """Determine which device entry to keep when there are duplicates.

    As we transitioned to new unique ids, we did not update existing device entries
    and as a result there are devices with both the old and new unique id format. We
    have to pick which one to keep, and preferably this can repair things if the
    user previously renamed devices.
    """
    # Prefer the new device if the user already gave it a name or area. Otherwise,
    # do the same for the old entry. If no entries have been modified then keep the new one.
    if new_entry.disabled_by is None and (
        new_entry.area_id is not None or new_entry.name_by_user is not None
    ):
        return new_entry
    if old_entry.disabled_by is None and (
        old_entry.area_id is not None or old_entry.name_by_user is not None
    ):
        return old_entry
    return new_entry if new_entry.disabled_by is None else old_entry


def _async_fix_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_id: str,
    mac_address: str,
    serial_number: str,
) -> None:
    """Migrate existing device identifiers to the new format.

    This will rename any device ids that are prefixed with the serial number to be prefixed
    with the mac address. This also cleans up from a bug that allowed devices to exist
    in both the old and new format.
    """
    device_entries = dr.async_entries_for_config_entry(device_registry, config_entry_id)
    device_entry_map = {}
    migrations = {}
    for device_entry in device_entries:
        unique_id = str(next(iter(device_entry.identifiers))[1])
        device_entry_map[unique_id] = device_entry
        if (suffix := unique_id.removeprefix(str(serial_number))) != unique_id:
            migrations[unique_id] = f"{mac_address}{suffix}"

    for unique_id, new_unique_id in migrations.items():
        old_entry = device_entry_map[unique_id]
        if (new_entry := device_entry_map.get(new_unique_id)) is not None:
            # Device entries exist for both the old and new format and one must be removed
            entry_to_keep = _async_device_entry_to_keep(old_entry, new_entry)
            if entry_to_keep == new_entry:
                _LOGGER.debug("Removing device entry %s", unique_id)
                device_registry.async_remove_device(old_entry.id)
                continue
            # Remove new entry and update old entry to new id below
            _LOGGER.debug("Removing device entry %s", new_unique_id)
            device_registry.async_remove_device(new_entry.id)

        _LOGGER.debug("Updating device id from %s to %s", unique_id, new_unique_id)
        device_registry.async_update_device(
            old_entry.id, new_identifiers={(DOMAIN, new_unique_id)}
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
