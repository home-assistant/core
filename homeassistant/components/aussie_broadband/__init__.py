"""The Aussie Broadband integration."""

from __future__ import annotations

from aiohttp import ClientError
from aussiebb.asyncio import AussieBB
from aussiebb.const import FETCH_TYPES
from aussiebb.exceptions import AuthenticationException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import AussieBroadandDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aussie Broadband from a config entry."""
    # Login to the Aussie Broadband API and retrieve the current service list
    client = AussieBB(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
    )

    # Ignore services that don't support usage data
    ignore_types = [*FETCH_TYPES, "Hardware"]

    try:
        await client.login()
        services = await client.get_services(drop_types=ignore_types)
    except AuthenticationException as exc:
        raise ConfigEntryAuthFailed from exc
    except ClientError as exc:
        raise ConfigEntryNotReady from exc

    # Initiate a Data Update Coordinator for each service
    for service in services:
        service["coordinator"] = AussieBroadandDataUpdateCoordinator(
            hass, client, service["service_id"]
        )
        await service["coordinator"].async_config_entry_first_refresh()

    # Setup the integration
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "services": services,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
