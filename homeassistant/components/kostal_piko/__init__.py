"""The Kostal Piko Solar Inverter integration."""
from __future__ import annotations

import logging
from typing import Any

from pykostalpiko import Piko
from pykostalpiko.dxs import get_value_by_descriptor as get_value
from pykostalpiko.dxs.inverter import (
    MODEL,
    NAME,
    SERIAL_NUMBER,
    Versions as version_descriptors,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kostal Piko Solar Inverter from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    piko = Piko(
        async_get_clientsession(hass),
        entry.data.get(CONF_HOST),
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )

    async def logout(*_: Any):
        _LOGGER.debug("Logging out of inverter session")
        await piko.async_logout()

    # Authenticate and logout if homeassistant is stopped
    _LOGGER.debug("Logging in to inverter session")
    await piko.async_login()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout)

    hass.data[DOMAIN][entry.entry_id] = piko

    device_registry = dr.async_get(hass)

    data = await piko.async_fetch_multiple(
        [
            NAME,
            MODEL,
            SERIAL_NUMBER,
            version_descriptors.FIRMWARE,
            version_descriptors.HARDWARE,
        ]
    )

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        default_manufacturer="Kostal",
        name=get_value(NAME, data),
        model=get_value(MODEL, data),
        identifiers={(DOMAIN, get_value(SERIAL_NUMBER, data))},
        sw_version=get_value(version_descriptors.FIRMWARE, data),
        hw_version=get_value(version_descriptors.HARDWARE, data),
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
