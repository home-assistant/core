"""Support for UPnP/IGD Sensors."""
from datetime import timedelta
from typing import Any, Mapping, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_BYTES, DATA_RATE_KIBIBYTES_PER_SECOND
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    CONFIG_ENTRY_SCAN_INTERVAL,
    CONFIG_ENTRY_UDN,
    DATA_PACKETS,
    DATA_RATE_PACKETS_PER_SECOND,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DOMAIN_COORDINATORS,
    DOMAIN_DEVICES,
    KIBIBYTE,
    LOGGER as _LOGGER,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    TIMESTAMP,
)
from .device import Device

SENSOR_TYPES = {
    BYTES_RECEIVED: {
        "device_value_key": BYTES_RECEIVED,
        "name": f"{DATA_BYTES} received",
        "unit": DATA_BYTES,
        "unique_id": BYTES_RECEIVED,
        "derived_name": f"{DATA_RATE_KIBIBYTES_PER_SECOND} received",
        "derived_unit": DATA_RATE_KIBIBYTES_PER_SECOND,
        "derived_unique_id": "KiB/sec_received",
    },
    BYTES_SENT: {
        "device_value_key": BYTES_SENT,
        "name": f"{DATA_BYTES} sent",
        "unit": DATA_BYTES,
        "unique_id": BYTES_SENT,
        "derived_name": f"{DATA_RATE_KIBIBYTES_PER_SECOND} sent",
        "derived_unit": DATA_RATE_KIBIBYTES_PER_SECOND,
        "derived_unique_id": "KiB/sec_sent",
    },
    PACKETS_RECEIVED: {
        "device_value_key": PACKETS_RECEIVED,
        "name": f"{DATA_PACKETS} received",
        "unit": DATA_PACKETS,
        "unique_id": PACKETS_RECEIVED,
        "derived_name": f"{DATA_RATE_PACKETS_PER_SECOND} received",
        "derived_unit": DATA_RATE_PACKETS_PER_SECOND,
        "derived_unique_id": "packets/sec_received",
    },
    PACKETS_SENT: {
        "device_value_key": PACKETS_SENT,
        "name": f"{DATA_PACKETS} sent",
        "unit": DATA_PACKETS,
        "unique_id": PACKETS_SENT,
        "derived_name": f"{DATA_RATE_PACKETS_PER_SECOND} sent",
        "derived_unit": DATA_RATE_PACKETS_PER_SECOND,
        "derived_unique_id": "packets/sec_sent",
    },
}


async def async_setup_platform(
    hass: HomeAssistantType, config, async_add_entities, discovery_info=None
) -> None:
    """Old way of setting up UPnP/IGD sensors."""
    _LOGGER.debug(
        "async_setup_platform: config: %s, discovery: %s", config, discovery_info
    )


async def async_setup_entry(
    hass, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the UPnP/IGD sensors."""
    udn = config_entry.data[CONFIG_ENTRY_UDN]
    device: Device = hass.data[DOMAIN][DOMAIN_DEVICES][udn]

    update_interval_sec = config_entry.options.get(
        CONFIG_ENTRY_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )
    update_interval = timedelta(seconds=update_interval_sec)
    _LOGGER.debug("update_interval: %s", update_interval)
    _LOGGER.debug("Adding sensors")
    coordinator = DataUpdateCoordinator[Mapping[str, Any]](
        hass,
        _LOGGER,
        name=device.name,
        update_method=device.async_get_traffic_data,
        update_interval=update_interval,
    )
    await coordinator.async_refresh()
    hass.data[DOMAIN][DOMAIN_COORDINATORS][udn] = coordinator

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


class UpnpSensor(CoordinatorEntity):
    """Base class for UPnP/IGD sensors."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Mapping[str, Any]],
        device: Device,
        sensor_type: Mapping[str, str],
        update_multiplier: int = 2,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._device = device
        self._sensor_type = sensor_type
        self._update_counter_max = update_multiplier
        self._update_counter = 0

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:server-network"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        device_value_key = self._sensor_type["device_value_key"]
        return (
            self.coordinator.last_update_success
            and device_value_key in self.coordinator.data
        )

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
    def device_info(self) -> Mapping[str, Any]:
        """Get device info."""
        return {
            "connections": {(dr.CONNECTION_UPNP, self._device.udn)},
            "name": self._device.name,
            "manufacturer": self._device.manufacturer,
            "model": self._device.model_name,
        }


class RawUpnpSensor(UpnpSensor):
    """Representation of a UPnP/IGD sensor."""

    @property
    def state(self) -> Optional[str]:
        """Return the state of the device."""
        device_value_key = self._sensor_type["device_value_key"]
        value = self.coordinator.data[device_value_key]
        if value is None:
            return None
        return format(value, "d")


class DerivedUpnpSensor(UpnpSensor):
    """Representation of a UNIT Sent/Received per second sensor."""

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
    def state(self) -> Optional[str]:
        """Return the state of the device."""
        # Can't calculate any derivative if we have only one value.
        device_value_key = self._sensor_type["device_value_key"]
        current_value = self.coordinator.data[device_value_key]
        if current_value is None:
            return None
        current_timestamp = self.coordinator.data[TIMESTAMP]
        if self._last_value is None or self._has_overflowed(current_value):
            self._last_value = current_value
            self._last_timestamp = current_timestamp
            return None

        # Calculate derivative.
        delta_value = current_value - self._last_value
        if self._sensor_type["unit"] == DATA_BYTES:
            delta_value /= KIBIBYTE
        delta_time = current_timestamp - self._last_timestamp
        if delta_time.seconds == 0:
            # Prevent division by 0.
            return None
        derived = delta_value / delta_time.seconds

        # Store current values for future use.
        self._last_value = current_value
        self._last_timestamp = current_timestamp

        return format(derived, ".1f")
