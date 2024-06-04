"""The Aladdin Connect Genie integration."""

from __future__ import annotations

from genie_partner_sdk.client import AladdinConnectClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AsyncConfigEntryAuth
from .coordinator import AladdinConnectCoordinator

PLATFORMS: list[Platform] = [Platform.COVER]

type AladdinConnectConfigEntry = ConfigEntry[AladdinConnectCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: AladdinConnectConfigEntry
) -> bool:
    """Set up Aladdin Connect Genie from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(async_get_clientsession(hass), session)
    coordinator = AladdinConnectCoordinator(hass, AladdinConnectClient(auth))

    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AladdinConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: AladdinConnectConfigEntry
) -> bool:
    """Migrate old config."""
    if config_entry.version < 2:
        config_entry.async_start_reauth(hass)
        hass.config_entries.async_update_entry(
            config_entry,
            version=2,
            minor_version=1,
        )

    return True
