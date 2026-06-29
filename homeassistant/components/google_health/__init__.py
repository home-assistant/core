"""The Google Health integration."""

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
from .coordinator import GoogleHealthCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type GoogleHealthConfigEntry = ConfigEntry[GoogleHealthCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleHealthConfigEntry
) -> bool:
    """Set up Google Health from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "OAuth2 implementation temporarily unavailable, will retry"
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
    coordinator = GoogleHealthCoordinator(hass, entry, api_client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleHealthConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
