"""The TISControl integration."""

from __future__ import annotations

import logging

from TISControlProtocol.api import TISApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DEVICES_DICT, DOMAIN

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TISControl from a config entry."""
    if DOMAIN not in hass.data:
        hass.data.setdefault(DOMAIN, {"tis_api": {}})
    tis_api = TISApi(
        port=int(entry.data["port"]),
        hass=hass,
        domain=DOMAIN,
        devices_dict=DEVICES_DICT,
    )

    hass.data[DOMAIN]["supported_platforms"] = PLATFORMS
    try:
        await tis_api.connect()
    except ConnectionError as e:
        logging.error("error connecting to TIS api %s", e)
        return False
    # add the tis api to the hass data
    hass.data[DOMAIN]["tis_api"] = tis_api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        api = hass.data[DOMAIN].get("tis_api", None)
        if api:
            hass.data[DOMAIN].pop("tis_api")
        return unload_ok
    return False
