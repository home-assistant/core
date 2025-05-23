"""Support for UPC ConnectBox router."""

from __future__ import annotations

import logging

from connect_box import ConnectBox
from connect_box.exceptions import ConnectBoxError, ConnectBoxLoginError
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = "192.168.0.1"

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string,
    }
)


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> UPCDeviceScanner | None:
    """Return the UPC device scanner."""
    conf = config[DEVICE_TRACKER_DOMAIN]
    session = async_get_clientsession(hass)
    connect_box = ConnectBox(session, conf[CONF_PASSWORD], host=conf[CONF_HOST])

    # Check login data
    try:
        await connect_box.async_initialize_token()
    except ConnectBoxLoginError:
        _LOGGER.error("ConnectBox login data error!")
        return None
    except ConnectBoxError:
        pass

    async def _shutdown(event):
        """Shutdown event."""
        await connect_box.async_close_session()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    return UPCDeviceScanner(connect_box)


class UPCDeviceScanner(DeviceScanner):
    """Class which queries a router running UPC ConnectBox firmware."""

    def __init__(self, connect_box: ConnectBox) -> None:
        """Initialize the scanner."""
        self.connect_box: ConnectBox = connect_box

    async def async_scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        try:
            await self.connect_box.async_get_devices()
        except ConnectBoxError:
            return []

        return [device.mac for device in self.connect_box.devices]

    async def async_get_device_name(self, device: str) -> str | None:
        """Get the device name (the name of the wireless device not used)."""
        for connected_device in self.connect_box.devices:
            if (
                connected_device.mac == device
                and connected_device.hostname.lower() != "unknown"
            ):
                return connected_device.hostname

        return None
