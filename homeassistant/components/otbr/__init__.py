"""The Open Thread Border Router integration."""
from __future__ import annotations

import dataclasses
from http import HTTPStatus

import aiohttp

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


class ThreadNetworkActiveError(HomeAssistantError):
    """Raised on attempts to modify the active dataset when thread network is active."""


class NoDatasetError(HomeAssistantError):
    """Raised on attempts to update a dataset which does not exist."""


def _async_get_thread_rest_service_url(hass) -> str:
    """Return Thread REST API URL."""
    otbr_data: OTBRData | None = hass.data.get(DOMAIN)
    if not otbr_data:
        raise HomeAssistantError("otbr not setup")

    return otbr_data.url


def _raise_for_status(response: aiohttp.ClientResponse) -> None:
    """Raise if status >= 400."""
    try:
        response.raise_for_status()
    except aiohttp.ClientResponseError as exc:
        raise HomeAssistantError(f"unexpected http status {response.status}") from exc


async def async_get_active_dataset_tlvs(hass: HomeAssistant) -> bytes | None:
    """Get current active operational dataset in TLVS format, or None.

    Returns None if there is no active operational dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """

    response = await async_get_clientsession(hass).get(
        f"{_async_get_thread_rest_service_url(hass)}/node/dataset/active",
        headers={"Accept": "text/plain"},
        timeout=aiohttp.ClientTimeout(total=10),
    )

    _raise_for_status(response)
    if response.status == HTTPStatus.NO_CONTENT:
        return None

    if response.status != HTTPStatus.OK:
        raise HomeAssistantError(f"unexpected http status {response.status}")

    try:
        tmp = await response.read()
        return bytes.fromhex(tmp.decode("ASCII"))
    except ValueError as exc:
        raise HomeAssistantError("unexpected API response") from exc
