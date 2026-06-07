"""Support for Unifi AP direct access."""

import logging

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the Unifi direct scanner."""
    scanner = UnifiDirectScanner(hass, config)
    return await scanner.async_update_and_report(async_see)


class UnifiDirectScanner:
    """Device scanner for UniFi access point clients."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize the scanner."""
        self._hass = hass
        self._ap = UniFiAP(
            target=config[CONF_HOST],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            port=config[CONF_PORT],
        )

    async def async_update_and_report(self, async_see: AsyncSeeCallback) -> bool:
        """Update the client info from AP and report to the tracker."""
        try:
            clients = await self._hass.async_add_executor_job(self._ap.get_clients)
        except UniFiAPConnectionException as e:
            _LOGGER.error("Failed to connect to accesspoint: %s", str(e))
            return False
        except UniFiAPDataException as e:
            _LOGGER.error("Failed to get proper response from accesspoint: %s", str(e))
            return False

        for mac, client_info in clients.items():
            await async_see(
                mac=mac,
                host_name=client_info.get("hostname"),
            )
        return True
