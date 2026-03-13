"""The saj component."""

from __future__ import annotations

import logging
from typing import Any

import pysaj

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONNECTION_TYPES

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type SAJConfigEntry = ConfigEntry[pysaj.SAJ]


async def async_setup_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Set up SAJ from a config entry."""
    host = entry.data[CONF_HOST]
    connection_type = entry.data[CONF_TYPE]
    username = entry.data.get(CONF_USERNAME, None)
    password = entry.data.get(CONF_PASSWORD, None)

    # Create SAJ connection
    kwargs: dict[str, Any] = {}
    wifi = connection_type == CONNECTION_TYPES[1]
    if wifi:
        kwargs["wifi"] = True
        if username:
            kwargs["username"] = username
        if password:
            kwargs["password"] = password

    async def _async_connect() -> pysaj.SAJ:
        """Connect to SAJ and verify connection."""
        saj = pysaj.SAJ(host, **kwargs)
        # Test connection by reading sensors
        sensor_def = pysaj.Sensors(wifi)
        done = await saj.read(sensor_def)
        if not done:
            raise ConfigEntryNotReady("Failed to read initial sensor data")
        return saj

    try:
        saj = await _async_connect()
    except pysaj.UnauthorizedException as err:
        _LOGGER.error("Username and/or password is wrong")
        raise ConfigEntryNotReady("Authentication failed") from err
    except pysaj.UnexpectedResponseException as err:
        _LOGGER.error(
            "Error in SAJ, please check host/ip address. Original error: %s", err
        )
        raise ConfigEntryNotReady(f"Connection error: {err}") from err
    except TimeoutError as err:
        _LOGGER.error("Connection timeout to SAJ at %s: %s", host, err)
        raise ConfigEntryNotReady(f"Connection timeout: {err}") from err
    except OSError as err:
        _LOGGER.error("Network error connecting to SAJ at %s: %s", host, err)
        raise ConfigEntryNotReady(f"Network error: {err}") from err

    # Store connection in runtime_data
    entry.runtime_data = saj

    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
