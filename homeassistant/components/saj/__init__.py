"""The saj component."""

from __future__ import annotations

from dataclasses import dataclass
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
from .coordinator import SAJDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass(frozen=True, slots=True)
class SAJRuntimeData:
    """Runtime data attached to a SAJ config entry."""

    saj: pysaj.SAJ
    coordinator: SAJDataUpdateCoordinator


type SAJConfigEntry = ConfigEntry[SAJRuntimeData]


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

    async def _async_connect() -> tuple[pysaj.SAJ, pysaj.Sensors]:
        """Connect to SAJ and verify connection."""
        saj = pysaj.SAJ(host, **kwargs)
        sensor_def = pysaj.Sensors(wifi)
        done = await saj.read(sensor_def)
        if not done:
            raise ConfigEntryNotReady("Failed to read initial sensor data")
        return saj, sensor_def

    try:
        saj, sensor_def = await _async_connect()
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

    coordinator = SAJDataUpdateCoordinator(hass, entry, saj, sensor_def)
    entry.runtime_data = SAJRuntimeData(saj=saj, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
