"""The Ubiquiti airOS integration."""

from __future__ import annotations

import logging

from airos.airos8 import AirOS
from airos.exceptions import (
    ConnectionAuthenticationError,
    ConnectionSetupError,
    DataMissingError,
    DeviceConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import AirOSDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

type AirOSConfigEntry = ConfigEntry[AirOS]


async def async_setup_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Set up Ubiquiti airOS from a config entry."""

    host = entry.data.get(CONF_HOST)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    session = async_get_clientsession(hass, verify_ssl=False)

    airos_device = AirOS(host, username, password, session)

    coordinator = AirOSDataUpdateCoordinator(hass, entry, airos_device)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    try:
        if not await airos_device.login():
            return False
    except (ConnectionSetupError, DeviceConnectionError, TimeoutError) as e:
        _LOGGER.error("Error connecting to airOS device: %s", e)
        return False
    except (
        ConnectionAuthenticationError,
        DataMissingError,
    ) as e:
        _LOGGER.error("Error authenticating with airOS device: %s", e)
        return False

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
