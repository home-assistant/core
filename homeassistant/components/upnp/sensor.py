"""Support for UPnP/IGD Sensors."""
from datetime import timedelta
import logging

from homeassistant.const import DATA_BYTES, DATA_KIBIBYTES, TIME_SECONDS
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from .const import DOMAIN as DOMAIN_UPNP, SIGNAL_REMOVE_SENSOR

_LOGGER = logging.getLogger(__name__)

BYTES_RECEIVED = "bytes_received"
BYTES_SENT = "bytes_sent"
PACKETS_RECEIVED = "packets_received"
PACKETS_SENT = "packets_sent"

SENSOR_TYPES = {
    BYTES_RECEIVED: {"name": "bytes received", "unit": DATA_BYTES},
    BYTES_SENT: {"name": "bytes sent", "unit": DATA_BYTES},
    PACKETS_RECEIVED: {"name": "packets received", "unit": "packets"},
    PACKETS_SENT: {"name": "packets sent", "unit": "packets"},
}

IN = "received"
OUT = "sent"
KIBIBYTE = 1024

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


async def async_setup_platform(
    hass: HomeAssistantType, config, async_add_entities, discovery_info=None
):
    """Old way of setting up UPnP/IGD sensors."""
    _LOGGER.debug(
        "async_setup_platform: config: %s, discovery: %s", config, discovery_info
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the UPnP/IGD sensor."""

    @callback
    def async_add_sensor(device):
        """Add sensors from UPnP/IGD device."""
        # raw sensors + per-second sensors
        sensors = [
            RawUPnPIGDSensor(device, name, sensor_type)
            for name, sensor_type in SENSOR_TYPES.items()
        ]
        sensors += [
            KBytePerSecondUPnPIGDSensor(device, IN),
            KBytePerSecondUPnPIGDSensor(device, OUT),
            PacketsPerSecondUPnPIGDSensor(device, IN),
            PacketsPerSecondUPnPIGDSensor(device, OUT),
        ]
        async_add_entities(sensors, True)

    data = config_entry.data
    if "udn" in data:
        udn = data["udn"]
    else:
        # any device will do
        udn = list(hass.data[DOMAIN_UPNP]["devices"].keys())[0]

    device = hass.data[DOMAIN_UPNP]["devices"][udn]
    async_add_sensor(device)


class UpnpSensor(Entity):
    """Base class for UPnP/IGD sensors."""

    def __init__(self, device):
        """Initialize the base sensor."""
        self._device = device

    async def async_added_to_hass(self):
        """Subscribe to sensors events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_REMOVE_SENSOR, self._upnp_remove_sensor
            )
        )

    @callback
    def _upnp_remove_sensor(self, device):
        """Remove sensor."""
        if self._device != device:
            # not for us
            return

        self.hass.async_create_task(self.async_remove())

    @property
    def device_info(self):
        """Get device info."""
        return {
            "connections": {(dr.CONNECTION_UPNP, self._device.udn)},
            "identifiers": {(DOMAIN_UPNP, self._device.udn)},
            "name": self._device.name,
            "manufacturer": self._device.manufacturer,
            "model": self._device.model_name,
        }


class RawUPnPIGDSensor(UpnpSensor):
    """Representation of a UPnP/IGD sensor."""

    def __init__(self, device, sensor_type_name, sensor_type):
        """Initialize the UPnP/IGD sensor."""
        super().__init__(device)
        self._type_name = sensor_type_name
        self._type = sensor_type
        self._name = "{} {}".format(device.name, sensor_type["name"])
        self._state = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._device.udn}_{self._type_name}"

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self._state is None:
            return None

        return format(self._state, "d")

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:server-network"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._type["unit"]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest information from the IGD."""
        if self._type_name == BYTES_RECEIVED:
            self._state = await self._device.async_get_total_bytes_received()
        elif self._type_name == BYTES_SENT:
            self._state = await self._device.async_get_total_bytes_sent()
        elif self._type_name == PACKETS_RECEIVED:
            self._state = await self._device.async_get_total_packets_received()
        elif self._type_name == PACKETS_SENT:
            self._state = await self._device.async_get_total_packets_sent()


class PerSecondUPnPIGDSensor(UpnpSensor):
    """Abstract representation of a X Sent/Received per second sensor."""

    def __init__(self, device, direction):
        """Initialize sensor."""
        super().__init__(device)
        self._direction = direction

        self._state = None
        self._last_value = None
        self._last_update_time = None

    @property
    def unit(self) -> str:
        """Get unit we are measuring in."""
        raise NotImplementedError()

    async def _async_fetch_value(self):
        """Fetch a value from the IGD."""
        raise NotImplementedError()

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._device.udn}_{self.unit}/sec_{self._direction}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device.name} {self.unit}/sec {self._direction}"

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:server-network"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return f"{self.unit}/{TIME_SECONDS}"

    def _is_overflowed(self, new_value) -> bool:
        """Check if value has overflowed."""
        return new_value < self._last_value

    async def async_update(self):
        """Get the latest information from the UPnP/IGD."""
        new_value = await self._async_fetch_value()

        if self._last_value is None:
            self._last_value = new_value
            self._last_update_time = dt_util.utcnow()
            return

        now = dt_util.utcnow()
        if self._is_overflowed(new_value):
            self._state = None  # temporarily report nothing
        else:
            delta_time = (now - self._last_update_time).seconds
            delta_value = new_value - self._last_value
            self._state = delta_value / delta_time

        self._last_value = new_value
        self._last_update_time = now


class KBytePerSecondUPnPIGDSensor(PerSecondUPnPIGDSensor):
    """Representation of a KBytes Sent/Received per second sensor."""

    @property
    def unit(self) -> str:
        """Get unit we are measuring in."""
        return DATA_KIBIBYTES

    async def _async_fetch_value(self) -> float:
        """Fetch value from device."""
        if self._direction == IN:
            return await self._device.async_get_total_bytes_received()

        return await self._device.async_get_total_bytes_sent()

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self._state is None:
            return None

        return format(float(self._state / KIBIBYTE), ".1f")


class PacketsPerSecondUPnPIGDSensor(PerSecondUPnPIGDSensor):
    """Representation of a Packets Sent/Received per second sensor."""

    @property
    def unit(self) -> str:
        """Get unit we are measuring in."""
        return "packets"

    async def _async_fetch_value(self) -> float:
        """Fetch value from device."""
        if self._direction == IN:
            return await self._device.async_get_total_packets_received()

        return await self._device.async_get_total_packets_sent()

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self._state is None:
            return None

        return format(float(self._state), ".1f")
