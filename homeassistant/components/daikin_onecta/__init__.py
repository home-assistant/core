"""Platform for the Daikin AC."""

import logging

import aiohttp
import jwt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .const import DOMAIN
from .coordinator import OnectaDataUpdateCoordinator
from .daikin_api import DaikinApi
from .device import (
    migrate_legacy_entity_unique_ids,
    migrate_legacy_subdevice_identifiers,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
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
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed from err
    except (OAuth2TokenRequestError, aiohttp.ClientError) as err:
        raise ConfigEntryNotReady from err

    config_entry.runtime_data = OnectaDataUpdateCoordinator(
        hass, config_entry, daikin_api
    )

    await config_entry.runtime_data.async_config_entry_first_refresh()
    migrate_legacy_subdevice_identifiers(
        hass, config_entry, config_entry.runtime_data.data or {}
    )
    migrate_legacy_entity_unique_ids(
        hass, config_entry, config_entry.runtime_data.data or {}
    )
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading integration")
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    coordinator.update_settings(config_entry)
    coordinator.async_update_listeners()


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.info(
        "Migration from version %s.%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version == 1:
        match config_entry.minor_version:
            case 1:
                try:
                    unique_id = jwt.decode(
                        config_entry.data["token"]["access_token"],
                        options={"verify_signature": False},
                    )["sub"]
                except jwt.DecodeError, KeyError:
                    _LOGGER.exception("Failed to decode JWT during migration")
                    return False
                hass.config_entries.async_update_entry(
                    config_entry,
                    minor_version=2,
                    unique_id=unique_id,
                )

    _LOGGER.info(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
