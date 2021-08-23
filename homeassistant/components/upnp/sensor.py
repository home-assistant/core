"""Support for UPnP/IGD Sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_BYTES, DATA_RATE_KIBIBYTES_PER_SECOND
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpnpDataUpdateCoordinator, UpnpEntity
from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    DATA_PACKETS,
    DATA_RATE_PACKETS_PER_SECOND,
    DOMAIN,
    KIBIBYTE,
    LOGGER,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    TIMESTAMP,
)

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
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
) -> None:
    """Old way of setting up UPnP/IGD sensors."""
    LOGGER.debug(
        "async_setup_platform: config: %s, discovery: %s", config, discovery_info
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPnP/IGD sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    LOGGER.debug("Adding sensors")

    sensors = [
        RawUpnpSensor(coordinator, SENSOR_TYPES[BYTES_RECEIVED]),
        RawUpnpSensor(coordinator, SENSOR_TYPES[BYTES_SENT]),
        RawUpnpSensor(coordinator, SENSOR_TYPES[PACKETS_RECEIVED]),
        RawUpnpSensor(coordinator, SENSOR_TYPES[PACKETS_SENT]),
        DerivedUpnpSensor(coordinator, SENSOR_TYPES[BYTES_RECEIVED]),
        DerivedUpnpSensor(coordinator, SENSOR_TYPES[BYTES_SENT]),
        DerivedUpnpSensor(coordinator, SENSOR_TYPES[PACKETS_RECEIVED]),
        DerivedUpnpSensor(coordinator, SENSOR_TYPES[PACKETS_SENT]),
    ]
    async_add_entities(sensors)


class UpnpSensor(UpnpEntity, SensorEntity):
    """Base class for UPnP/IGD sensors."""

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
        sensor_type: dict[str, str],
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = f"{coordinator.device.name} {sensor_type['name']}"
        self._attr_unique_id = f"{coordinator.device.udn}_{sensor_type['unique_id']}"

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return "mdi:server-network"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.get(
            self._sensor_type["device_value_key"]
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._sensor_type["unit"]


class RawUpnpSensor(UpnpSensor):
    """Representation of a UPnP/IGD sensor."""

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        device_value_key = self._sensor_type["device_value_key"]
        value = self.coordinator.data[device_value_key]
        if value is None:
            return None
        return format(value, "d")


class DerivedUpnpSensor(UpnpSensor):
    """Representation of a UNIT Sent/Received per second sensor."""

    def __init__(self, coordinator: UpnpDataUpdateCoordinator, sensor_type) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, sensor_type)
        self._last_value = None
        self._last_timestamp = None
        self._attr_name = f"{coordinator.device.name} {sensor_type['derived_name']}"
        self._attr_unique_id = (
            f"{coordinator.device.udn}_{sensor_type['derived_unique_id']}"
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._sensor_type["derived_unit"]

    def _has_overflowed(self, current_value) -> bool:
        """Check if value has overflowed."""
        return current_value < self._last_value

    @property
    def native_value(self) -> str | None:
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
        if delta_time.total_seconds() == 0:
            # Prevent division by 0.
            return None
        derived = delta_value / delta_time.total_seconds()

        # Store current values for future use.
        self._last_value = current_value
        self._last_timestamp = current_timestamp

        return format(derived, ".1f")
