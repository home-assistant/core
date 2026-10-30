"""Heiman Home Assistant integration."""

import logging

from heimanconnect import HeimanMQTTError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import HeimanApiClient
from .const import PLATFORMS
from .coordinator import HeimanDataUpdateCoordinator

type HeimanConfigEntry = ConfigEntry[HeimanDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Set up Heiman from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady("OAuth2 implementation unavailable") from err

    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed(
            "OAuth2 authentication failed, re-authentication required"
        ) from err
    except OAuth2TokenRequestError as err:
        raise ConfigEntryNotReady(f"OAuth2 token request failed: {err}") from err
    except ValueError as err:
        _LOGGER.error(
            "OAuth2 token validation failed: %s. "
            "The refresh token may have expired. Please re-authenticate",
            err,
        )
        raise ConfigEntryAuthFailed("Token expired") from err

    api_client = HeimanApiClient(hass=hass, session=session)

    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=api_client,
        config_entry=entry,
        oauth_session=session,
    )
    entry.async_on_unload(coordinator.async_shutdown)

    await coordinator.async_config_entry_first_refresh()

    # Initialize MQTT client after successful first refresh. A transient
    # broker outage must be retried by Home Assistant instead of leaving
    # the config entry in a setup error state.
    try:
        await coordinator.async_init_mqtt_client()
    except HeimanMQTTError as err:
        raise ConfigEntryNotReady(f"MQTT connection failed: {err}") from err

    # Set runtime_data only after successful initialization
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    # The coordinator's resources are released by async_shutdown, which is
    # registered with entry.async_on_unload during setup.
    return True
