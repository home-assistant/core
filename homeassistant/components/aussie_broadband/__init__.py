"""The Aussie Broadband integration."""
from __future__ import annotations

from aiohttp import ClientError
from aussiebb.asyncio import AussieBB, AuthenticationException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SERVICES, DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aussie Broadband from a config entry."""

    # Login to the Aussie Broadband API and retrieve the current service list
    try:
        client = AussieBB(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            async_get_clientsession(hass),
        )
        await client.login()
        all_services = await client.get_services()

    except AuthenticationException as exc:
        raise ConfigEntryAuthFailed() from exc
    except ClientError as exc:
        raise ConfigEntryNotReady() from exc

    # Filter the service list to those that are enabled in options
    services = [
        s for s in all_services if str(s["service_id"]) in entry.options[CONF_SERVICES]
    ]

    # Setup the integration
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "services": services,
    }
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Reload to update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
