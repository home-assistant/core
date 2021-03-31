"""Code to handle a Xiaomi Gateway."""
import logging

from miio import DeviceException, gateway

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

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
            # get the gateway info
            self._gateway_info = await self._hass.async_add_executor_job(
                self._gateway_device.info
            )
            # get the connected sub devices
            await self._hass.async_add_executor_job(
                self._gateway_device.discover_devices
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


class XiaomiGatewayDevice(CoordinatorEntity, Entity):
    """Representation of a base Xiaomi Gateway Device."""

    def __init__(self, coordinator, sub_device, entry):
        """Initialize the Xiaomi Gateway Device."""
        super().__init__(coordinator)
        self._sub_device = sub_device
        self._entry = entry
        self._unique_id = sub_device.sid
        self._name = f"{sub_device.name} ({sub_device.sid})"

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def device_info(self):
        """Return the device info of the gateway."""
        return {
            "identifiers": {(DOMAIN, self._sub_device.sid)},
            "via_device": (DOMAIN, self._entry.unique_id),
            "manufacturer": "Xiaomi",
            "name": self._sub_device.name,
            "model": self._sub_device.model,
            "sw_version": self._sub_device.firmware_version,
        }
