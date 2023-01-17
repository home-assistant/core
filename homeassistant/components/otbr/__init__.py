"""The Open Thread Border Router integration."""
from __future__ import annotations

import dataclasses

import python_otbr_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


@dataclasses.dataclass
class OTBRData:
    """Container for OTBR data."""

    url: str


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Open Thread Border Router config entry."""

    hass.data[DOMAIN] = OTBRData(entry.data["url"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN)
    return True


def _async_get_thread_rest_service_url(hass) -> str:
    """Return Thread REST API URL."""
    otbr_data: OTBRData | None = hass.data.get(DOMAIN)
    if not otbr_data:
        raise HomeAssistantError("otbr not setup")

    return otbr_data.url


async def async_get_active_dataset_tlvs(hass: HomeAssistant) -> bytes | None:
    """Get current active operational dataset in TLVS format, or None.

    Returns None if there is no active operational dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """

    api = python_otbr_api.OTBR(
        _async_get_thread_rest_service_url(hass), async_get_clientsession(hass), 10
    )
    try:
        return await api.get_active_dataset_tlvs()
    except python_otbr_api.OTBRError as exc:
        raise HomeAssistantError("Failed to call OTBR API") from exc
