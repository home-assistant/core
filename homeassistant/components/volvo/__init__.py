"""The Volvo integration."""

from __future__ import annotations

import asyncio

from aiohttp import ClientResponseError
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import VolvoAuthException, VolvoCarsVehicle

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import VolvoAuth
from .const import CONF_VIN, DOMAIN, PLATFORMS
from .coordinator import (
    VolvoConfigEntry,
    VolvoMediumIntervalCoordinator,
    VolvoSlowIntervalCoordinator,
    VolvoVerySlowIntervalCoordinator,
)


async def async_setup_entry(hass: HomeAssistant, entry: VolvoConfigEntry) -> bool:
    """Set up Volvo from a config entry."""

    api = await _async_auth_and_create_api(hass, entry)
    vehicle = await _async_load_vehicle(api)

    # Order is important! Faster intervals must come first.
    coordinators = (
        VolvoMediumIntervalCoordinator(hass, entry, api, vehicle),
        VolvoSlowIntervalCoordinator(hass, entry, api, vehicle),
        VolvoVerySlowIntervalCoordinator(hass, entry, api, vehicle),
    )

    await asyncio.gather(*(c.async_config_entry_first_refresh() for c in coordinators))

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VolvoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_auth_and_create_api(
    hass: HomeAssistant, entry: VolvoConfigEntry
) -> VolvoCarsApi:
    implementation = await async_get_config_entry_implementation(hass, entry)
    oauth_session = OAuth2Session(hass, entry, implementation)
    web_session = async_get_clientsession(hass)
    auth = VolvoAuth(web_session, oauth_session)

    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        if err.status in (400, 401):
            raise ConfigEntryAuthFailed from err

        raise ConfigEntryNotReady from err

    return VolvoCarsApi(
        web_session,
        auth,
        entry.data[CONF_API_KEY],
        entry.data[CONF_VIN],
    )


async def _async_load_vehicle(api: VolvoCarsApi) -> VolvoCarsVehicle:
    try:
        vehicle = await api.async_get_vehicle_details()
    except VolvoAuthException as ex:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="unauthorized",
            translation_placeholders={"message": ex.message},
        ) from ex

    if vehicle is None:
        raise ConfigEntryError(translation_domain=DOMAIN, translation_key="no_vehicle")

    return vehicle
