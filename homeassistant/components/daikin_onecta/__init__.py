"""Platform for the Daikin AC."""

import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, OAuth2TokenRequestError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .const import DOMAIN
from .coordinator import OnectaDataUpdateCoordinator
from .daikin_api import DaikinApi

_LOGGER = logging.getLogger(__name__)

type DaikinOnectaConfigEntry = ConfigEntry[OnectaDataUpdateCoordinator]

PLATFORMS = [
    Platform.CLIMATE,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> bool:
    """Establish connection with Daikin."""
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, config_entry
            )
        )
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    daikin_api = DaikinApi(hass, config_entry, implementation)

    try:
        await daikin_api.async_get_access_token()
    except (OAuth2TokenRequestError, TimeoutError, aiohttp.ClientError) as err:
        raise ConfigEntryNotReady from err

    config_entry.runtime_data = OnectaDataUpdateCoordinator(
        hass, config_entry, daikin_api
    )

    await config_entry.runtime_data.async_config_entry_first_refresh()
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading integration")
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> None:
    """Handle options update."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    if coordinator.update_settings(config_entry):
        await coordinator.async_request_refresh()
        coordinator.async_update_listeners()
