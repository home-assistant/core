"""The Nintendo Switch Parental Controls integration."""

from __future__ import annotations

from pynintendoparental import Authenticator
from pynintendoparental.exceptions import (
    InvalidOAuthConfigurationException,
    InvalidSessionTokenException,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError

from .const import CONF_SESSION_TOKEN
from .coordinator import NintendoParentalConfigEntry, NintendoUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: NintendoParentalConfigEntry
) -> bool:
    """Set up Nintendo Switch Parental Controls from a config entry."""
    try:
        nintendo_auth = await Authenticator.complete_login(
            auth=None,
            response_token=entry.data[CONF_SESSION_TOKEN],
            is_session_token=True,
        )
    except InvalidSessionTokenException as err:
        raise ConfigEntryAuthFailed(err) from err
    except InvalidOAuthConfigurationException as err:
        raise ConfigEntryError(err) from err
    entry.runtime_data = coordinator = NintendoUpdateCoordinator(
        hass, nintendo_auth, entry
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NintendoParentalConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
