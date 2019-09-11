"""Support for UPC ConnectBox router."""
import logging
from typing import Optional, List

import voluptuous as vol
from connect_box import ConnectBox
from connect_box.exceptions import ConnectBoxError, ConnectBoxLoginError

from homeassistant.components.device_tracker import PLATFORM_SCHEMA, DeviceScanner
from homeassistant.const import CONF_HOST, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CMD_DEVICES = 123

DEFAULT_IP = "192.168.0.1"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string,
    }
)


async def async_get_scanner(hass, config):
    """Return the UPC device scanner."""
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    connect_box = ConnectBox(session, config[CONF_PASSWORD], host=config[CONF_HOST])

    # Check login data
    try:
        await connect_box.async_initialize_token()
    except ConnectBoxLoginError:
        _LOGGER.error("ConnectBox login data error!")
        return None
    except ConnectBoxError:
        pass

    return UPCDeviceScanner(connect_box)


class UPCDeviceScanner(DeviceScanner):
    """This class queries a router running UPC ConnectBox firmware."""

    def __init__(self, connect_box: ConnectBox):
        """Initialize the scanner."""
        self.connect_box: ConnectBox = connect_box

    async def async_scan_devices(self) -> List[str]:
        """Scan for new devices and return a list with found device IDs."""
        try:
            await self.connect_box.async_get_devices()
        except ConnectBoxError:
            return []

        return [device.mac for device in self.connect_box.devices]

    async def async_get_device_name(self, device: str) -> Optional[str]:
        """Get the device name (the name of the wireless device not used)."""
        for connected_device in self.connect_box.devices:
            if connected_device != device:
                continue
            return connected_device.hostname

        return None
