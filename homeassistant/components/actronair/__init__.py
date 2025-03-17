"""The Actron Air integration."""

from __future__ import annotations

import logging

from actronair_api import ActronAirApi, ApiException
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import AC_SYSTEMS_COORDINATOR, DOMAIN, SYSTEM_STATUS_COORDINATOR
from .coordinator import (
    ActronAirACSystemsDataCoordinator,
    ActronAirSystemStatusDataCoordinator,
)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SELECT]
_LOGGER = logging.getLogger(__name__)
ACTRON_AIR_SYNC_INTERVAL = 10
REQUEST_REFRESH_DELAY = 0.5

type ActronAirAuthConfigEntry = ConfigEntry[api.AsyncConfigEntryAuth]


async def async_setup_entry(
    hass: HomeAssistant, entry: ActronAirAuthConfigEntry
) -> bool:
    """Set up Actron Air from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    aa_api = ActronAirApi(
        api.AsyncConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session)
    )

    acSystemsCoordinator = ActronAirACSystemsDataCoordinator(hass, aa_api)
    acSystemStatusCoordinator = ActronAirSystemStatusDataCoordinator(hass, aa_api)

    try:
        await acSystemsCoordinator.async_config_entry_first_refresh()
        await acSystemStatusCoordinator.async_config_entry_first_refresh()
    except ApiException as err:
        raise ConfigEntryNotReady from err

    hass.config_entries.async_update_entry(
        entry, unique_id=acSystemsCoordinator.get_unique_id()
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        AC_SYSTEMS_COORDINATOR: acSystemsCoordinator,
        SYSTEM_STATUS_COORDINATOR: acSystemStatusCoordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ActronAirAuthConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
