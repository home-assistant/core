"""The Yoto integration."""

import aiohttp

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, OAuth2TokenRequestError
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import DOMAIN
from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: YotoConfigEntry) -> bool:
    """Set up Yoto from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err
    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except (aiohttp.ClientError, OAuth2TokenRequestError) as err:
        raise ConfigEntryNotReady from err

    coordinator = YotoDataUpdateCoordinator(hass, entry, session)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: YotoConfigEntry) -> bool:
    """Unload a Yoto config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
