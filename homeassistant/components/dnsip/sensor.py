"""Get the IP address of a given host."""
from __future__ import annotations

from datetime import timedelta
import logging
import socket
from typing import Final

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_HOSTNAME, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME: Final = "My IP"
SCAN_INTERVAL = timedelta(seconds=120)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the DNS IP sensor."""
    hostname: str = config[CONF_HOSTNAME]
    name: str = config[CONF_NAME]

    async_add_entities([DnsIPSensor(name, hostname)], True)

class DnsIPSensor(SensorEntity):
    """Implementation of a DNS IP sensor."""

    def __init__(self, name: str, hostname: str) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        self._hostname = hostname
        self._attr_icon = "mdi:web"
        self._attr_native_value = None # Initialize default

    @property
    def native_value(self) -> str | None:
        """Return the IP address of the given hostname."""
        return self._attr_native_value

    async def async_update(self) -> None:
        """Fetch the IP address of the given hostname."""
        try:
            # We use the executor job to run blocking socket calls
            self._attr_native_value = await self.hass.async_add_executor_job(
                socket.gethostbyname, self._hostname
            )
        except socket.gaierror:
            _LOGGER.warning("Cannot resolve hostname: %s", self._hostname)
            self._attr_native_value = None







            