"""Code to handle a Xiaomi Gateway."""
import logging

from miio import DeviceException, gateway

_LOGGER = logging.getLogger(__name__)


class ConnectXiaomiGateway:
    """Class to async connect to a Xiaomi Gateway."""

    def __init__(self, hass):
        """Initialize the entity."""
        self._hass = hass
        self._gateway_device = None
        self._gateway_info = None

    @property
    def gateway_device(self):
        """Return the class containing all connections to the gateway."""
        return self._gateway_device

    @property
    def gateway_info(self):
        """Return the class containing gateway info."""
        return self._gateway_info

    async def async_connect_gateway(self, host, token):
        """Connect to the Xiaomi Gateway."""
        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])
        try:
            self._gateway_device = gateway.Gateway(host, token)
            self._gateway_info = await self._hass.async_add_executor_job(
                self._gateway_device.info
            )
        except DeviceException:
            _LOGGER.error(
                "DeviceException during setup of xiaomi gateway with host %s", host
            )
            return False
        _LOGGER.debug(
            "%s %s %s detected",
            self._gateway_info.model,
            self._gateway_info.firmware_version,
            self._gateway_info.hardware_version,
        )
        return True
