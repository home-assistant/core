"""The victronvenus integration."""

from __future__ import annotations

import logging

from victronvenusclient import (
    CannotConnectError,
    Hub as VictronVenusHub,
    InvalidAuthError,
)

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from ._victron_integration import VictronVenusConfigEntry
from .const import CONF_INSTALLATION_ID, CONF_MODEL, CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

__all__ = ["DOMAIN", "async_setup_entry", "async_unload_entry"]


async def async_setup_entry(
    hass: HomeAssistant, entry: VictronVenusConfigEntry
) -> bool:
    """Set up victronvenus from a config entry."""

    config = entry.data
    hub = VictronVenusHub(
        config.get(CONF_HOST),
        config.get(CONF_PORT, 1883),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_SSL, False),
        config.get(CONF_INSTALLATION_ID),
        config.get(CONF_MODEL),
        config.get(CONF_SERIAL),
    )

    try:
        await hub.connect()
        await hub.initialize_devices_and_metrics()
        entry.runtime_data = hub
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    except InvalidAuthError as auth_error:
        _LOGGER.error("Invalid authentication")
        raise ConfigEntryAuthFailed("Invalid authentication") from auth_error
    except CannotConnectError as connect_error:
        _LOGGER.error("Cannot connect to the hub")
        raise ConfigEntryNotReady("Device is offline") from connect_error
    else:
        return True


async def async_unload_entry(
    hass: HomeAssistant, entry: VictronVenusConfigEntry
) -> bool:
    """Unload a config entry."""
    if hasattr(entry, "runtime_data"):
        hub = entry.runtime_data
        if hub is not None:
            if isinstance(hub, VictronVenusHub):
                await hub.disconnect()
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True
