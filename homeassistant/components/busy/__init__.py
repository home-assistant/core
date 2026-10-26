"""The BUSY Bar integration."""

import logging

from busylib import AsyncBusyBar
from busylib.exceptions import BusyBarError
from busylib.transports import AiohttpTransport

from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import BusyConfigEntry, BusyCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BusyConfigEntry) -> None:
    """Set up BUSY Bar from a config entry."""
    coordinator = BusyCoordinator(hass, entry)
    entry.async_on_unload(coordinator.client.aclose)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: BusyConfigEntry) -> None:
    """Unload BUSY Bar sensors."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BusyConfigEntry) -> None:
    """Revoke the entry's access token."""
    try:
        async with AsyncBusyBar(
            entry.data[CONF_HOST],
            token=entry.data[CONF_TOKEN],
            transport=AiohttpTransport(async_get_clientsession(hass)),
            timeout=10,
        ) as client:
            await client.access_tokens_revoke(entry.data[CONF_TOKEN][:8])
    except BusyBarError, OSError:
        _LOGGER.warning("Unable to revoke BUSY Bar access token; remove it on the bar")
