"""The Aussie Broadband integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientError
from aussiebb.asyncio import AussieBB, AuthenticationException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SERVICES, DEFAULT_UPDATE_INTERVAL, DOMAIN, SERVICE_ID

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aussie Broadband from a config entry."""
    # Login to the Aussie Broadband API and retrieve the current service list
    client = AussieBB(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    try:
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

    # Create an appropriate refresh function
    def update_data_factory(service_id):
        async def async_update_data():
            return await client.get_usage(service_id)

        return async_update_data

    # Initiate a Data Update Coordinator for each service
    for service in services:
        service["coordinator"] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=service["service_id"],
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
            update_method=update_data_factory(service[SERVICE_ID]),
        )
        await service["coordinator"].async_config_entry_first_refresh()

    # Setup the integration
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "services": services,
    }
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload to update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
