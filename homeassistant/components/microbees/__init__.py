"""The microBees integration."""

from dataclasses import dataclass
from http import HTTPStatus
import logging

import aiohttp
from microBeesPy.microbees import MicroBees

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from .const import ACCESS_TOKEN, BEES, CONNECTOR, COORDINATOR, DOMAIN, PLATFORMS
from .coordinator import MicroBeesUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up microBees from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as ex:
        if ex.status in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        ):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
        raise ConfigEntryNotReady from ex
    microbees = MicroBees(token=session.token[ACCESS_TOKEN])
    coordinator = MicroBeesUpdateCoordinator(hass, microbees)
    try:
        bees = await microbees.getBees()
    except Exception as ex:
        raise ConfigEntryNotReady from ex
    hass.data[DOMAIN] = {
        entry.entry_id: {
            BEES: bees,
            CONNECTOR: microbees,
            COORDINATOR: coordinator,
        }
    }

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)


    return unload_ok
