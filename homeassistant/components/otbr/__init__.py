"""The Open Thread Border Router integration."""
from __future__ import annotations

import dataclasses

import python_otbr_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN


@dataclasses.dataclass
class OTBRData:
    """Container for OTBR data."""

    url: str
    api: python_otbr_api.OTBR


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Open Thread Border Router component."""
    websocket_api.async_setup(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Open Thread Border Router config entry."""
    api = python_otbr_api.OTBR(entry.data["url"], async_get_clientsession(hass), 10)
    try:
        await api.get_active_dataset_tlvs()
    except python_otbr_api.OTBRError as exc:
        raise ConfigEntryNotReady from exc

    hass.data[DOMAIN] = OTBRData(entry.data["url"], api)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN)
    return True


async def async_get_active_dataset_tlvs(hass: HomeAssistant) -> bytes | None:
    """Get current active operational dataset in TLVS format, or None.

    Returns None if there is no active operational dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """
    if DOMAIN not in hass.data:
        raise HomeAssistantError("OTBR API not available")

    api: python_otbr_api.OTBR = hass.data[DOMAIN].api

    try:
        return await api.get_active_dataset_tlvs()
    except python_otbr_api.OTBRError as exc:
        raise HomeAssistantError("Failed to call OTBR API") from exc
