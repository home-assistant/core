"""UniFi Network config entry abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import ssl
from typing import Literal, Self

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from ..const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CLIENT_SOURCE,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_WIRED_BUG,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_DEVICES,
    DEFAULT_ALLOW_BANDWIDTH_SENSORS,
    DEFAULT_ALLOW_UPTIME_SENSORS,
    DEFAULT_DETECTION_TIME,
    DEFAULT_DPI_RESTRICTIONS,
    DEFAULT_IGNORE_WIRED_BUG,
    DEFAULT_TRACK_DEVICES,
)


@dataclass
class UnifiConfig:
    """Represent a UniFi config entry."""

    entry: ConfigEntry

    host: str
    port: int
    username: str
    password: str
    site: str
    ssl_context: ssl.SSLContext | Literal[False]

    option_tracked_clients: list[str]
    """Allow creating entities from clients."""

    # Device tracker options

    option_track_devices: bool
    """Config entry option to track UniFi devices."""
    option_ssid_filter: set[str]
    """Config entry option listing SSIDs used to track wireless clients."""
    option_detection_time: timedelta
    """Config entry option defining number of seconds from last seen to away"""
    option_ignore_wired_bug: bool
    """Config entry option to ignore wired bug."""

    # Client control options

    option_block_clients: list[str]
    """Config entry option with list of clients to control network access."""
    option_dpi_restrictions: bool
    """Config entry option to control DPI restriction groups."""

    # Statistics sensor options

    option_allow_bandwidth_sensors: bool
    """Config entry option to allow bandwidth sensors."""
    option_allow_uptime_sensors: bool
    """Config entry option to allow uptime sensors."""

    @classmethod
    def from_config_entry(cls, config_entry: ConfigEntry) -> Self:
        """Create object from config entry."""
        config = config_entry.data
        options = config_entry.options
        return cls(
            entry=config_entry,
            host=config[CONF_HOST],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            port=config[CONF_PORT],
            site=config[CONF_SITE_ID],
            ssl_context=config.get(CONF_VERIFY_SSL, False),
            option_tracked_clients=options.get(CONF_CLIENT_SOURCE, []),
            option_track_devices=options.get(CONF_TRACK_DEVICES, DEFAULT_TRACK_DEVICES),
            option_ssid_filter=set(options.get(CONF_SSID_FILTER, [])),
            option_detection_time=timedelta(
                seconds=options.get(CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME)
            ),
            option_ignore_wired_bug=options.get(
                CONF_IGNORE_WIRED_BUG, DEFAULT_IGNORE_WIRED_BUG
            ),
            option_block_clients=options.get(CONF_BLOCK_CLIENT, []),
            option_dpi_restrictions=options.get(
                CONF_DPI_RESTRICTIONS, DEFAULT_DPI_RESTRICTIONS
            ),
            option_allow_bandwidth_sensors=options.get(
                CONF_ALLOW_BANDWIDTH_SENSORS, DEFAULT_ALLOW_BANDWIDTH_SENSORS
            ),
            option_allow_uptime_sensors=options.get(
                CONF_ALLOW_UPTIME_SENSORS, DEFAULT_ALLOW_UPTIME_SENSORS
            ),
        )
