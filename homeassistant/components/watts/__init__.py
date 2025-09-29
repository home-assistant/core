"""The Watts Vision + integration."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
import logging

from aiohttp import ClientError, ClientResponseError
from visionpluspython.auth import WattsVisionAuth
from visionpluspython.client import WattsVisionClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import UpdateFailed

from .coordinator import WattsVisionCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


@dataclass
class WattsVisionRuntimeData:
    """Runtime data for Watts Vision integration."""

    auth: WattsVisionAuth
    coordinator: WattsVisionCoordinator
    client: WattsVisionClient


type WattsVisionConfigEntry = ConfigEntry[WattsVisionRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: WattsVisionConfigEntry) -> bool:
    """Set up Watts Vision from a config entry."""

    _LOGGER.debug("Setting up Watts Vision integration")

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    try:
        await oauth_session.async_ensure_token_valid()
    except ClientResponseError as err:
        if HTTPStatus.BAD_REQUEST <= err.status < HTTPStatus.INTERNAL_SERVER_ERROR:
            raise ConfigEntryAuthFailed("OAuth session not valid") from err
        raise ConfigEntryNotReady("Temporary connection error") from err
    except ClientError as err:
        raise ConfigEntryNotReady("Network issue during OAuth setup") from err

    session = aiohttp_client.async_get_clientsession(hass)
    auth = WattsVisionAuth(
        oauth_session=oauth_session,
        session=session,
    )

    client = WattsVisionClient(auth)
    coordinator = WattsVisionCoordinator(hass, client, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady("Failed to fetch initial data") from err

    entry.runtime_data = WattsVisionRuntimeData(
        auth=auth,
        coordinator=coordinator,
        client=client,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WattsVisionConfigEntry
) -> bool:
    """Unload a config entry."""

    _LOGGER.debug("Unloading Watts Vision + integration")

    unload_result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if not unload_result:
        _LOGGER.error("Failed to unload platforms for Watts Vision + integration")
    else:
        _LOGGER.debug("Successfully unloaded platforms for Watts Vision + integration")

    return unload_result
