"""Code to handle a Motion Gateway."""
import logging
import socket

from motionblinds import MotionGateway

_LOGGER = logging.getLogger(__name__)


class ConnectMotionGateway:
    """Class to async connect to a Motion Gateway."""

    def __init__(self, hass, multicast):
        """Initialize the entity."""
        self._hass = hass
        self._multicast = multicast
        self._gateway_device = None

    @property
    def gateway_device(self):
        """Return the class containing all connections to the gateway."""
        return self._gateway_device

    def update_gateway(self):
        """Update all information of the gateway."""
        self.gateway_device.GetDeviceList()
        self.gateway_device.Update()
        for blind in self.gateway_device.device_list.values():
            blind.Update_from_cache()

    async def async_connect_gateway(self, host, key):
        """Connect to the Motion Gateway."""
        _LOGGER.debug("Initializing with host %s (key %s)", host, key[:3])
        self._gateway_device = MotionGateway(
            ip=host, key=key, multicast=self._multicast
        )
        try:
            # update device info and get the connected sub devices
            await self._hass.async_add_executor_job(self.update_gateway)
        except socket.timeout:
            _LOGGER.error(
                "Timeout trying to connect to Motion Gateway with host %s", host
            )
            return False
        _LOGGER.debug(
            "Motion gateway mac: %s, protocol: %s detected",
            self.gateway_device.mac,
            self.gateway_device.protocol,
        )
        return True
