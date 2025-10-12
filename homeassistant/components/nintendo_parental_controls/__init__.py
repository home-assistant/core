"""The Nintendo Switch parental controls integration."""

from __future__ import annotations

from pynintendoparental import Authenticator
from pynintendoparental.exceptions import (
    InvalidOAuthConfigurationException,
    InvalidSessionTokenException,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SESSION_TOKEN, DOMAIN
from .coordinator import NintendoParentalControlsConfigEntry, NintendoUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.TIME]


async def async_setup_entry(
    hass: HomeAssistant, entry: NintendoParentalControlsConfigEntry
) -> bool:
    """Set up Nintendo Switch parental controls from a config entry."""
    try:
        nintendo_auth = await Authenticator.complete_login(
            auth=None,
            response_token=entry.data[CONF_SESSION_TOKEN],
            is_session_token=True,
            client_session=async_get_clientsession(hass),
        )
    except (InvalidSessionTokenException, InvalidOAuthConfigurationException) as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_expired",
        ) from err
    entry.runtime_data = coordinator = NintendoUpdateCoordinator(
        hass, nintendo_auth, entry
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NintendoParentalControlsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
