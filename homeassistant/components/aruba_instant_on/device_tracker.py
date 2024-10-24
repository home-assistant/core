"""Support for Aruba Instant On Access Points."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from ion_client import Client
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .consts import CONF_SITE_ID

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SITE_ID): cv.string,
    }
)


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> ArubaInstantOnDeviceScanner | None:
    """Validate the configuration and return a Aruba Instant On scanner."""
    scanner = ArubaInstantOnDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class ArubaInstantOnDeviceScanner(DeviceScanner):
    """Query the Aruba Instant On API for connected devices."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the scanner."""
        self.client = Client(
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
        )
        self.site_id = config[CONF_SITE_ID]
        self.last_results: dict[str, dict[str, str]] = {}
        self.success_init = self._update_info()

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return list(self.last_results)

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        return self.last_results.get(device, {}).get("name")

    def _update_info(self) -> bool:
        """Ensure the information from the Aruba Instant On API is up to date.

        Return true if scanning successful.
        """
        try:
            clients = self.client.json(f"/sites/{self.site_id}/clientSummary")
            self.last_results = {
                client["id"]: {"mac": client["id"], "name": client["name"]}
                for client in clients.get("elements", [])
            }
        except httpx.HTTPError as e:
            _LOGGER.error("Aruba Instant On API error: %s", e)
            return False

        return True
