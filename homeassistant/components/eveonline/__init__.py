"""The Eve Online integration."""

from __future__ import annotations

from eveonline import EveOnlineClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AsyncConfigEntryAuth
from .const import DOMAIN
from .coordinator import EveOnlineConfigEntry, EveOnlineCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EveOnlineConfigEntry) -> bool:
    """Set up Eve Online from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = OAuth2Session(hass, entry, implementation)

    auth = AsyncConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session)
    client = EveOnlineClient(auth=auth)

    character_id: int = entry.data["character_id"]
    character_name: str = entry.data["character_name"]

    coordinator = EveOnlineCoordinator(
        hass, entry, client, character_id, character_name
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EveOnlineConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
