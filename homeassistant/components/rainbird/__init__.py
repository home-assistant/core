"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from pyrainbird.async_client import AsyncRainbirdClient, AsyncRainbirdController
from pyrainbird.exceptions import RainbirdApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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

    if entry.unique_id is None:
        await _fix_unique_id(hass, controller, entry)

    try:
        model_info = await controller.get_model_and_version()
    except RainbirdApiException as err:
        raise ConfigEntryNotReady from err

    data = RainbirdData(hass, entry, controller, model_info)
    await data.coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _fix_unique_id(
    hass: HomeAssistant, controller: AsyncRainbirdController, entry: ConfigEntry
):
    """Update the config entry with a unique id based on the mac address."""
    try:
        wifi_params = await controller.get_wifi_params()
    except RainbirdApiException as err:
        _LOGGER.warning("Unable to fix missing unique id: %s", err)
        return

    if (new_unique_id := wifi_params.mac_address) is None:
        _LOGGER.warning("Unable to fix missing unique id (was None)")
        return

    entries = hass.config_entries.async_entries(DOMAIN)
    for existing_entry in entries:
        if existing_entry.unique_id == new_unique_id:
            _LOGGER.warning("Unable to fix missing unique id (already exists)")
            return

    _LOGGER.debug("Updating unique id to %s", new_unique_id)
    hass.config_entries.async_update_entry(
        entry,
        unique_id=new_unique_id,
        data={
            **entry.data,
            CONF_MAC: wifi_params.mac_address,
        },
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
