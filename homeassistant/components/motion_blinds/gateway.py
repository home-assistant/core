"""Code to handle a Motion Gateway."""
import logging
import socket

from motionblinds import MotionGateway, AsyncMotionMulticast

_LOGGER = logging.getLogger(__name__)


class ConnectMotionGateway:
    """Class to async connect to a Motion Gateway."""

    def __init__(self, hass, multicast = None, interface = None):
        """Initialize the entity."""
        self._hass = hass
        self._multicast = multicast
        self._gateway_device = None
        self._interface = interface
        self._interfaces = []

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

    def check_interface(self):
        """check if the current interface supports multicast."""
        try:
            return self.gateway_device.Check_gateway_multicast()
        except socket.timeout:
            return False

    async def async_get_interfaces(self):
        """Get list of interface to use."""
        interfaces = [DEFAULT_INTERFACE, "0.0.0.0"]
        enabled_interfaces = []
        default_interface = DEFAULT_INTERFACE

        adapters = await network.async_get_adapters(self.hass)
        for adapter in adapters:
            if ipv4s := adapter["ipv4"]:
                ip4 = ipv4s[0]["address"]
                interfaces.append(ip4)
                if adapter["enabled"]:
                    enabled_interfaces.append(ip4)
                    if adapter["default"]:
                        default_interface = ip4

        if len(enabled_interfaces) == 1:
            default_interface = enabled_interfaces[0]
            interfaces.remove(default_interface)
            interfaces.insert(0, default_interface)

        if self._interface is not None:
            interfaces.remove(self._interface)
            interfaces.insert(0, self._interface)

        return interfaces

    async def async_check_interface(self, host, key):
        """Connect to the Motion Gateway."""
        self._interfaces = await self.async_get_interfaces()
        for interface in self._interfaces:
            _LOGGER.debug("Checking Motion Blinds interface '%s' with host %s", interface, host)
            # initialize multicast listener
            check_multicast = AsyncMotionMulticast(interface=interface)
            try:
                await check_multicast.Start_listen()
            except gaierror:
                continue

            # trigger test multicast
            self.gateway_device = MotionGateway(
                ip=host, key=key, multicast=check_multicast
            )
            result = await self._hass.async_add_executor_job(self.check_interface)

            # close multicast listener again
            try:
                await check_multicast.Stop_listen()
            except gaierror:
                continue

            if result:
                # succesfully received multicast
                return interface

        _LOGGER.error("Could not find working interface for Motion Blinds host %s, using interface '%s'", host, self._interface)
        return self._interface
