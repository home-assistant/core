"""The QNAP QSW integration."""
from __future__ import annotations

import logging

from aioqsw.localapi import ConnectionOptions, QnapQswApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, QSW_COORD_DATA, QSW_COORD_FW
from .coordinator import QswDataCoordinator, QswFirmwareCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up QNAP QSW from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    qsw = QnapQswApi(aiohttp_client.async_get_clientsession(hass), options)

    coord_data = QswDataCoordinator(hass, qsw)
    await coord_data.async_config_entry_first_refresh()

    coord_fw = QswFirmwareCoordinator(hass, qsw)
    try:
        await coord_fw.async_config_entry_first_refresh()
    except ConfigEntryNotReady as error:
        _LOGGER.warning(error)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        QSW_COORD_DATA: coord_data,
        QSW_COORD_FW: coord_fw,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
