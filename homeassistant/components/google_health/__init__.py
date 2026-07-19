"""The Google Health integration."""

import asyncio
from dataclasses import dataclass
from typing import Any

from google_health_api import GoogleHealthApi
from google_health_api.const import HealthApiScope

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from . import api
from .const import DOMAIN
from .coordinator import (
    GoogleHealthActivityCoordinator,
    GoogleHealthBodyCoordinator,
    GoogleHealthDataUpdateCoordinator,
    GoogleHealthSleepCoordinator,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class GoogleHealthData:
    """Class to hold Google Health coordinators."""

    activity_coordinator: GoogleHealthActivityCoordinator | None = None
    body_coordinator: GoogleHealthBodyCoordinator | None = None
    sleep_coordinator: GoogleHealthSleepCoordinator | None = None


type GoogleHealthConfigEntry = ConfigEntry[GoogleHealthData]


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleHealthConfigEntry
) -> bool:
    """Set up Google Health from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth_error",
        ) from err

    session = OAuth2Session(hass, entry, implementation)

    scopes = session.token.get("scope", "").split()
    if HealthApiScope.PROFILE_READ not in scopes:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="missing_profile_scope",
        )

    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    api_client = GoogleHealthApi(auth)

    coordinators: list[GoogleHealthDataUpdateCoordinator[Any]] = []

    activity_coordinator = None
    if all(scope in scopes for scope in api_client.steps.required_read_scopes):
        activity_coordinator = GoogleHealthActivityCoordinator(hass, entry, api_client)
        coordinators.append(activity_coordinator)

    body_coordinator = None
    if all(scope in scopes for scope in api_client.weight.required_read_scopes):
        body_coordinator = GoogleHealthBodyCoordinator(hass, entry, api_client)
        coordinators.append(body_coordinator)

    sleep_coordinator = None
    if all(scope in scopes for scope in api_client.sleep.required_read_scopes):
        sleep_coordinator = GoogleHealthSleepCoordinator(hass, entry, api_client)
        coordinators.append(sleep_coordinator)

    if coordinators:
        await asyncio.gather(
            *(coord.async_config_entry_first_refresh() for coord in coordinators)
        )

    entry.runtime_data = GoogleHealthData(
        activity_coordinator=activity_coordinator,
        body_coordinator=body_coordinator,
        sleep_coordinator=sleep_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleHealthConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
