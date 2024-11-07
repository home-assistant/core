"""Support for Unifi AP direct access."""

from __future__ import annotations

import logging
from typing import Any

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSH_PORT = 22

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> UnifiDeviceScanner | None:
    """Validate the configuration and return a Unifi direct scanner."""
    scanner = UnifiDeviceScanner(config[DEVICE_TRACKER_DOMAIN])
    return scanner if scanner.update_clients() else None


class UnifiDeviceScanner(DeviceScanner):
    """Class which queries Unifi wireless access point."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the scanner."""
        self.clients: dict[str, dict[str, Any]] = {}
        self.ap = UniFiAP(
            target=config[CONF_HOST],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            port=config[CONF_PORT],
        )

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self.update_clients()
        return list(self.clients)

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        client_info = self.clients.get(device)
        if client_info:
            return client_info.get("hostname")
        return None

    def update_clients(self) -> bool:
        """Update the client info from AP."""
        try:
            self.clients = self.ap.get_clients()
        except UniFiAPConnectionException:
            _LOGGER.error("Failed to connect to accesspoint")
            return False
        except UniFiAPDataException:
            _LOGGER.error("Failed to get proper response from accesspoint")
            return False

        return True
