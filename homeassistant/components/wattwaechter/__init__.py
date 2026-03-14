"""The WattWächter Plus integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from aio_wattwaechter import Wattwaechter, WattwaechterConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import WattwaechterCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.UPDATE]

type WattwaechterConfigEntry = ConfigEntry[WattwaechterCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: WattwaechterConfigEntry
) -> bool:
    """Set up WattWächter Plus from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data.get(CONF_TOKEN)

    session = async_get_clientsession(hass)
    client = Wattwaechter(host, token=token, session=session)

    # Verify device is reachable
    try:
        await client.alive()
    except WattwaechterConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host},
        ) from err

    coordinator = WattwaechterCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Update listener for options changes (e.g. scan interval)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: WattwaechterConfigEntry
) -> None:
    """Handle options update - dynamically adjust coordinator interval."""
    coordinator = entry.runtime_data
    new_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator.update_interval = timedelta(seconds=new_interval)
    await coordinator.async_request_refresh()


async def async_unload_entry(
    hass: HomeAssistant, entry: WattwaechterConfigEntry
) -> bool:
    """Unload a WattWächter Plus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
