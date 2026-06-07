"""Support for Unifi AP direct access."""
import logging
from datetime import timedelta

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSH_PORT = 22
SCAN_INTERVAL = timedelta(seconds=30)

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
    async_see,
    discovery_info: DiscoveryInfoType | None = None,
) -> list:
    """Set up the Unifi direct scanner."""
    return [UnifiDirectScannerEntity(config)]


class UnifiDirectScannerEntity(ScannerEntity):
    """Scanner for UniFi access point clients."""

    _attr_should_poll = True
    _attr_scan_interval = SCAN_INTERVAL

    def __init__(self, config: ConfigType) -> None:
        """Initialize the scanner."""
        self._ap = UniFiAP(
            target=config[CONF_HOST],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            port=config[CONF_PORT],
        )

    @property
    def name(self) -> str:
        """Return the name of the scanner."""
        return "UniFi Direct Scanner"

    async def async_update(self) -> None:
        """Update the client info from AP."""
        try:
            clients = await self.hass.async_add_executor_job(self._ap.get_clients)
        except UniFiAPConnectionException as e:
            _LOGGER.error("Failed to connect to accesspoint: %s", str(e))
            return
        except UniFiAPDataException as e:
            _LOGGER.error("Failed to get proper response from accesspoint: %s", str(e))
            return

        for mac, client_info in clients.items():
            await self.async_see(
                mac=mac,
                host_name=client_info.get("hostname"),
            )
