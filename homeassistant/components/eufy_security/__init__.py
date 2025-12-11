"""The Eufy Security integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnectError, EufySecurityError, async_connect
from .const import DOMAIN, PLATFORMS
from .coordinator import (
    EufySecurityConfigEntry,
    EufySecurityCoordinator,
    EufySecurityData,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: EufySecurityConfigEntry
) -> bool:
    """Set up Eufy Security from a config entry."""
    session = async_get_clientsession(hass)

    try:
        api = await async_connect(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            session,
        )
    except CannotConnectError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except EufySecurityError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    coordinator = EufySecurityCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = EufySecurityData(
        api=api,
        devices={
            "cameras": {camera.serial: camera for camera in api.cameras.values()},
            "stations": {station.serial: station for station in api.stations.values()},
        },
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EufySecurityConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Disconnect from WebSocket server
        await entry.runtime_data.api.async_disconnect()

    return unload_ok
