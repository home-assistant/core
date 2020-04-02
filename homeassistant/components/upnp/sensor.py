"""Support for UPnP/IGD Sensors."""
from datetime import timedelta
from typing import Mapping

from homeassistant.const import (
    DATA_BYTES,
    DATA_RATE_KIBIBYTES_PER_SECOND,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    DATA_PACKETS,
    DATA_RATE_PACKETS_PER_SECOND,
    DOMAIN,
    KIBIBYTE,
    LOGGER as _LOGGER,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    SIGNAL_REMOVE_DEVICE,
    TIMESTAMP,
)
from .device import Device

SENSOR_TYPES = {
    BYTES_RECEIVED: {
        "device_value_key": BYTES_RECEIVED,
        "name": DATA_BYTES + " received",
        "unit": DATA_BYTES,
        "unique_id": BYTES_RECEIVED,
        "derived_name": DATA_RATE_KIBIBYTES_PER_SECOND + " received",
        "derived_unit": DATA_RATE_KIBIBYTES_PER_SECOND,
        "derived_unique_id": "KiB/sec_received",
    },
    BYTES_SENT: {
        "device_value_key": BYTES_SENT,
        "name": DATA_BYTES + " sent",
        "unit": DATA_BYTES,
        "unique_id": BYTES_SENT,
        "derived_name": DATA_RATE_KIBIBYTES_PER_SECOND + " sent",
        "derived_unit": DATA_RATE_KIBIBYTES_PER_SECOND,
        "derived_unique_id": "KiB/sec_sent",
    },
    PACKETS_RECEIVED: {
        "device_value_key": PACKETS_RECEIVED,
        "name": DATA_PACKETS + " received",
        "unit": DATA_PACKETS,
        "unique_id": PACKETS_RECEIVED,
        "derived_name": DATA_RATE_PACKETS_PER_SECOND + " received",
        "derived_unit": DATA_RATE_PACKETS_PER_SECOND,
        "derived_unique_id": "packets/sec_received",
    },
    PACKETS_SENT: {
        "device_value_key": PACKETS_SENT,
        "name": DATA_PACKETS + " sent",
        "unit": DATA_PACKETS,
        "unique_id": PACKETS_SENT,
        "derived_name": DATA_RATE_PACKETS_PER_SECOND + " sent",
        "derived_unit": DATA_RATE_PACKETS_PER_SECOND,
        "derived_unique_id": "packets/sec_sent",
    },
}

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(
    hass: HomeAssistantType, config, async_add_entities, discovery_info=None
) -> None:
    """Old way of setting up UPnP/IGD sensors."""
    _LOGGER.debug(
        "async_setup_platform: config: %s, discovery: %s", config, discovery_info
    )


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up the UPnP/IGD sensor."""
    data = config_entry.data
    if "udn" in data:
        udn = data["udn"]
    else:
        # any device will do
        udn = list(hass.data[DOMAIN]["devices"].keys())[0]

    device = hass.data[DOMAIN]["devices"][udn]  # type: Device

    _LOGGER.debug("Adding sensors")
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=device.name,
        update_method=device.async_get_traffic_data,
        update_interval=timedelta(seconds=SCAN_INTERVAL.seconds),
    )
    await coordinator.async_refresh()

    sensors = [
        RawUpnpSensor(coordinator, device, SENSOR_TYPES[BYTES_RECEIVED]),
        RawUpnpSensor(coordinator, device, SENSOR_TYPES[BYTES_SENT]),
        RawUpnpSensor(coordinator, device, SENSOR_TYPES[PACKETS_RECEIVED]),
        RawUpnpSensor(coordinator, device, SENSOR_TYPES[PACKETS_SENT]),
        DerivedUpnpSensor(coordinator, device, SENSOR_TYPES[BYTES_RECEIVED]),
        DerivedUpnpSensor(coordinator, device, SENSOR_TYPES[BYTES_SENT]),
        DerivedUpnpSensor(coordinator, device, SENSOR_TYPES[PACKETS_RECEIVED]),
        DerivedUpnpSensor(coordinator, device, SENSOR_TYPES[PACKETS_SENT]),
    ]
    async_add_entities(sensors, True)


class UpnpSensor(Entity):
    """Base class for UPnP/IGD sensors."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: Device,
        sensor_type: Mapping[str, str],
    ) -> None:
        """Initialize the base sensor."""
        self._coordinator = coordinator
        self._device = device
        self._sensor_type = sensor_type

    @property
    def should_poll(self) -> bool:
        """Inform we should not be polled."""
        return False

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:server-network"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device.name} {self._sensor_type['name']}"

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._device.udn}_{self._sensor_type['unique_id']}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._sensor_type["unit"]

    @property
    def device_info(self) -> Mapping[str, any]:
        """Get device info."""
        return {
            "connections": {(dr.CONNECTION_UPNP, self._device.udn)},
            "name": self._device.name,
            "manufacturer": self._device.manufacturer,
            "model": self._device.model_name,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to sensors events."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_REMOVE_DEVICE, self._async_upnp_remove_sensor
            )
        )

    async def _async_upnp_remove_sensor(self, device) -> None:
        """Remove sensor."""
        if self._device != device:
            # not for us
            return

        _LOGGER.debug("Removing sensor: %s", self.unique_id)
        await self.hass.async_create_task(self.async_remove())

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        self._coordinator.async_remove_listener(self.async_write_ha_state)


class RawUpnpSensor(UpnpSensor):
    """Representation of a UPnP/IGD sensor."""

    @property
    def state(self) -> str:
        """Return the state of the device."""
        device_value_key = self._sensor_type["device_value_key"]
        value = self._coordinator.data[device_value_key]
        return format(value, "d")


class DerivedUpnpSensor(UpnpSensor):
    """Abstract representation of a UNIT Sent/Received per second sensor."""

    def __init__(self, coordinator, device, sensor_type) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, device, sensor_type)
        self._last_value = None
        self._last_timestamp = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device.name} {self._sensor_type['derived_name']}"

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._device.udn}_{self._sensor_type['derived_unique_id']}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._sensor_type["derived_unit"]

    def _has_overflowed(self, current_value) -> bool:
        """Check if value has overflowed."""
        return current_value < self._last_value

    @property
    def state(self) -> str:
        """Return the state of the device."""
        # Can't calculate any derivative if we have only one value.
        device_value_key = self._sensor_type["device_value_key"]
        current_value = self._coordinator.data[device_value_key]
        current_timestamp = self._coordinator.data[TIMESTAMP]
        if self._last_value is None or self._has_overflowed(current_value):
            self._last_value = current_value
            self._last_timestamp = current_timestamp
            return None

        # Calculate derivative.
        delta_value = current_value - self._last_value
        if self._sensor_type["unit"] == DATA_BYTES:
            delta_value /= KIBIBYTE
        delta_time = current_timestamp - self._last_timestamp
        derived = delta_value / delta_time.seconds

        # Store current values for future use.
        self._last_value = current_value
        self._last_timestamp = current_timestamp

        return format(derived, ".1f")
