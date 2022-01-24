"""The bemfa integration."""
from __future__ import annotations

import hashlib
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_INCLUDE_ENTITIES, CONF_UID, DOMAIN
from .mqtt import BemfaMqtt

_LOGGING = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bemfa from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    mqtt = await hass.async_add_executor_job(
        BemfaMqtt,
        hass,
        entry.data.get(CONF_UID),
        entry.data.get(CONF_INCLUDE_ENTITIES),
    )
    hass.data[DOMAIN][entry.entry_id] = {
        "uid_md5": hashlib.md5(entry.data[CONF_UID].encode("utf-8")).hexdigest(),
        "mqtt": mqtt,
    }

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data is not None:
        await hass.async_add_executor_job(data["mqtt"].disconnect)
        hass.data[DOMAIN].pop(entry.entry_id)

    return True
