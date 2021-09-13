"""Support for UPnP/IGD Sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_BYTES, DATA_RATE_KIBIBYTES_PER_SECOND, TIME_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpnpDataUpdateCoordinator, UpnpEntity, UpnpSensorEntityDescription
from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    DATA_PACKETS,
    DATA_RATE_PACKETS_PER_SECOND,
    DOMAIN,
    KIBIBYTE,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    ROUTER_IP,
    ROUTER_UPTIME,
    TIMESTAMP,
    WAN_STATUS,
)

RAW_SENSORS: tuple[UpnpSensorEntityDescription, ...] = (
    UpnpSensorEntityDescription(
        key=BYTES_RECEIVED,
        name=f"{DATA_BYTES} received",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_BYTES,
        format="d",
    ),
    UpnpSensorEntityDescription(
        key=BYTES_SENT,
        name=f"{DATA_BYTES} sent",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_BYTES,
        format="d",
    ),
    UpnpSensorEntityDescription(
        key=PACKETS_RECEIVED,
        name=f"{DATA_PACKETS} received",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_PACKETS,
        format="d",
    ),
    UpnpSensorEntityDescription(
        key=PACKETS_SENT,
        name=f"{DATA_PACKETS} sent",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_PACKETS,
        format="d",
    ),
    UpnpSensorEntityDescription(
        key=ROUTER_IP,
        name="External IP",
        icon="mdi:server-network",
    ),
    UpnpSensorEntityDescription(
        key=ROUTER_UPTIME,
        name="Uptime",
        icon="mdi:server-network",
        native_unit_of_measurement=TIME_SECONDS,
        entity_registry_enabled_default=False,
        format="d",
    ),
    UpnpSensorEntityDescription(
        key=WAN_STATUS,
        name="wan status",
        icon="mdi:server-network",
    ),
)

DERIVED_SENSORS: tuple[UpnpSensorEntityDescription, ...] = (
    UpnpSensorEntityDescription(
        key="KiB/sec_received",
        name=f"{DATA_RATE_KIBIBYTES_PER_SECOND} received",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_RATE_KIBIBYTES_PER_SECOND,
        format=".1f",
    ),
    UpnpSensorEntityDescription(
        key="KiB/sent",
        name=f"{DATA_RATE_KIBIBYTES_PER_SECOND} sent",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_RATE_KIBIBYTES_PER_SECOND,
        format=".1f",
    ),
    UpnpSensorEntityDescription(
        key="packets/sec_received",
        name=f"{DATA_RATE_PACKETS_PER_SECOND} received",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_RATE_PACKETS_PER_SECOND,
        format=".1f",
    ),
    UpnpSensorEntityDescription(
        key="packets/sent",
        name=f"{DATA_RATE_PACKETS_PER_SECOND} sent",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_RATE_PACKETS_PER_SECOND,
        format=".1f",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPnP/IGD sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[UpnpSensor] = [
        RawUpnpSensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in RAW_SENSORS
        if coordinator.data.get(entity_description.key) is not None
    ]
    entities.extend(
        [
            DerivedUpnpSensor(
                coordinator=coordinator,
                entity_description=entity_description,
            )
            for entity_description in DERIVED_SENSORS
            if coordinator.data.get(entity_description.key) is not None
        ]
    )

    async_add_entities(entities)


class UpnpSensor(UpnpEntity, SensorEntity):
    """Base class for UPnP/IGD sensors."""


class RawUpnpSensor(UpnpSensor):
    """Representation of a UPnP/IGD sensor."""

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        value = self.coordinator.data[self.entity_description.key]
        if value is None:
            return None
        return format(value, self.entity_description.format)


class DerivedUpnpSensor(UpnpSensor):
    """Representation of a UNIT Sent/Received per second sensor."""

    entity_description: UpnpSensorEntityDescription

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
        entity_description: UpnpSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator=coordinator, entity_description=entity_description)
        self._last_value = None
        self._last_timestamp = None

    def _has_overflowed(self, current_value) -> bool:
        """Check if value has overflowed."""
        return current_value < self._last_value

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        # Can't calculate any derivative if we have only one value.
        current_value = self.coordinator.data[self.entity_description.key]
        if current_value is None:
            return None
        current_timestamp = self.coordinator.data[TIMESTAMP]
        if self._last_value is None or self._has_overflowed(current_value):
            self._last_value = current_value
            self._last_timestamp = current_timestamp
            return None

        # Calculate derivative.
        delta_value = current_value - self._last_value
        if self.entity_description.native_unit_of_measurement == DATA_BYTES:
            delta_value /= KIBIBYTE
        delta_time = current_timestamp - self._last_timestamp
        if delta_time.total_seconds() == 0:
            # Prevent division by 0.
            return None
        derived = delta_value / delta_time.total_seconds()

        # Store current values for future use.
        self._last_value = current_value
        self._last_timestamp = current_timestamp

        return format(derived, self.entity_description.format)
