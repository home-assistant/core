"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from pyrainbird.async_client import AsyncRainbirdClient, AsyncRainbirdController
from pyrainbird.exceptions import RainbirdApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_registry import async_entries_for_config_entry

from .const import CONF_SERIAL_NUMBER
from .coordinator import RainbirdData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.CALENDAR,
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
    entity_entries = async_entries_for_config_entry(entity_registry, config_entry_id)
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
