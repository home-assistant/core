"""The Open Thread Border Router integration."""
from __future__ import annotations

import dataclasses
from http import HTTPStatus
from json import JSONDecodeError

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .models import OperationalDataSet, ThreadState


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


async def _async_get_thread_rest_service_url(hass) -> str:
    """Return Thread REST API URL."""
    otbr_data: OTBRData | None = hass.data.get(DOMAIN)
    if not otbr_data:
        raise HomeAssistantError

    return otbr_data.url


def _raise_for_status(response: aiohttp.ClientResponse) -> None:
    """Raise if status >= 400."""
    try:
        response.raise_for_status()
    except aiohttp.ClientResponseError as exc:
        raise HomeAssistantError from exc


async def async_get_thread_state(hass: HomeAssistant) -> ThreadState:
    """Get current Thread state."""

    response = await async_get_clientsession(hass).get(
        f"{await _async_get_thread_rest_service_url(hass)}/node/state",
        timeout=aiohttp.ClientTimeout(total=10),
    )

    _raise_for_status(response)
    if response.status != HTTPStatus.OK:
        raise HomeAssistantError

    try:
        state = ThreadState(int(await response.read()))
    except (TypeError, ValueError) as exc:
        raise HomeAssistantError from exc

    return state


async def async_set_thread_state(hass: HomeAssistant, state: ThreadState) -> None:
    """Set current Thread state."""

    response = await async_get_clientsession(hass).post(
        f"{await _async_get_thread_rest_service_url(hass)}/node/state",
        data=str(state.value),
        timeout=aiohttp.ClientTimeout(total=10),
    )

    _raise_for_status(response)
    if response.status != HTTPStatus.OK:
        raise HomeAssistantError


async def async_get_active_dataset(hass: HomeAssistant) -> OperationalDataSet | None:
    """Get current active operational dataset.

    Returns None if there is no active operational dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """

    response = await async_get_clientsession(hass).get(
        f"{await _async_get_thread_rest_service_url(hass)}/node/dataset/active",
        timeout=aiohttp.ClientTimeout(total=10),
    )

    _raise_for_status(response)
    if response.status == HTTPStatus.NO_CONTENT:
        return None

    if response.status != HTTPStatus.OK:
        raise HomeAssistantError

    try:
        return OperationalDataSet.from_json(await response.json())
    except (JSONDecodeError, vol.Error) as exc:
        raise HomeAssistantError from exc


async def async_get_active_dataset_tlvs(hass: HomeAssistant) -> bytes | None:
    """Get current active operational dataset in TLVS format, or None.

    Returns None if there is no active operational dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """

    response = await async_get_clientsession(hass).get(
        f"{await _async_get_thread_rest_service_url(hass)}/node/dataset/active",
        headers={"Accept": "text/plain"},
        timeout=aiohttp.ClientTimeout(total=10),
    )

    _raise_for_status(response)
    if response.status == HTTPStatus.NO_CONTENT:
        return None

    if response.status != HTTPStatus.OK:
        raise HomeAssistantError

    try:
        tmp = await response.read()
        return bytes.fromhex(tmp.decode("ASCII"))
    except ValueError as exc:
        raise HomeAssistantError from exc


async def async_create_active_dataset(
    hass: HomeAssistant, dataset: OperationalDataSet
) -> None:
    """Create active operational dataset.

    The passed in OperationalDataSet does not need to be fully populated, any fields
    not set will be automatically set by the open thread border router.
    Raises if the http status is 400 or higher or if the response is invalid.
    """

    response = await async_get_clientsession(hass).post(
        f"{await _async_get_thread_rest_service_url(hass)}/node/dataset/active",
        json=dataset.as_json(),
        timeout=aiohttp.ClientTimeout(total=10),
    )

    if response.status == HTTPStatus.CONFLICT:
        raise ThreadNetworkActiveError
    _raise_for_status(response)
    if response.status != HTTPStatus.ACCEPTED:
        raise HomeAssistantError


async def async_set_active_dataset(
    hass: HomeAssistant, dataset: OperationalDataSet
) -> None:
    """Set current active operational dataset.

    The passed in OperationalDataSet does not need to be fully populated, any fields
    not set will be automatically copied from the current active dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """

    response = await async_get_clientsession(hass).put(
        f"{await _async_get_thread_rest_service_url(hass)}/node/dataset/active",
        json=dataset.as_json(),
        timeout=aiohttp.ClientTimeout(total=10),
    )

    if response.status == HTTPStatus.NOT_FOUND:
        raise NoDatasetError
    if response.status == HTTPStatus.CONFLICT:
        raise ThreadNetworkActiveError
    _raise_for_status(response)
    if response.status != HTTPStatus.ACCEPTED:
        raise HomeAssistantError


async def async_set_active_dataset_tlvs(hass: HomeAssistant, dataset: bytes) -> None:
    """Set current active operational dataset.

    The passed in OperationalDataSet does not need to be fully populated, any fields
    not set will be automatically copied from the current active dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """

    response = await async_get_clientsession(hass).put(
        f"{await _async_get_thread_rest_service_url(hass)}/node/dataset/active",
        data=dataset.hex(),
        headers={"Content-Type": "text/plain"},
        timeout=aiohttp.ClientTimeout(total=10),
    )

    if response.status == HTTPStatus.NOT_FOUND:
        raise NoDatasetError
    if response.status == HTTPStatus.CONFLICT:
        raise ThreadNetworkActiveError
    _raise_for_status(response)
    if response.status != HTTPStatus.ACCEPTED:
        raise HomeAssistantError
