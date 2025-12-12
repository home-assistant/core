"""The homelink integration."""

from __future__ import annotations

from homelink.mqtt_provider import MQTTProvider

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import oauth2
from .const import DOMAIN
from .coordinator import HomeLinkConfigEntry, HomeLinkCoordinator

PLATFORMS: list[Platform] = [Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: HomeLinkConfigEntry) -> bool:
    """Set up homelink from a config entry."""
    auth_implementation = oauth2.SRPAuthImplementation(hass, DOMAIN)

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, auth_implementation
    )

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    authenticated_session = oauth2.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    provider = MQTTProvider(authenticated_session)
    coordinator = HomeLinkCoordinator(hass, provider, entry)

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, coordinator.async_on_unload
        )
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomeLinkConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_on_unload(None)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
