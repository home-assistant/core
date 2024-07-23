"""The TISControl integration."""

from __future__ import annotations

import logging

from TISControlProtocol.mock_api import TISApi

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
        # this vlaue is not used,to be removed
        "0.0.0.0",
        int(entry.data["port"]),
        "0.0.0.0",
        hass,
        DOMAIN,
        DEVICES_DICT,
        display_logo="./homeassistant/components/tis_control/logo.png",
    )

    hass.data[DOMAIN]["supported_platforms"] = PLATFORMS
    hass.data[DOMAIN]["discovered_devices"] = []

    try:
        await tis_api.connect()
    except Exception as e:  # noqa: BLE001, F841
        logging.info("error connecting to TIS api %s", e)
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
