"""Support for UPnP/IGD Sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_BYTES, DATA_RATE_KIBIBYTES_PER_SECOND, TIME_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpnpDataUpdateCoordinator, UpnpEntity
from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    DATA_PACKETS,
    DATA_RATE_PACKETS_PER_SECOND,
    DERIVED_SENSOR,
    DOMAIN,
    KIBIBYTE,
    LOGGER,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    RAW_SENSOR,
    ROUTER_IP,
    ROUTER_UPTIME,
    TIMESTAMP,
    WAN_STATUS,
)


@dataclass
class UpnpSensorEntityDescription(SensorEntityDescription):
    """A class that describes UPnP entities."""

    format: str = "s"


SENSOR_ENTITY_DESCRIPTIONS: dict[str, list[UpnpSensorEntityDescription]] = {
    RAW_SENSOR: [
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
            name="IP",
            icon="mdi:server-network",
            format="s",
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
            format="s",
        ),
    ],
    DERIVED_SENSOR: [
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
    ],
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

    entities = []
    entities.append(
        RawUpnpSensor(
            coordinator=coordinator,
            sensor_entity=sensor_entity,
        )
        for sensor_entity in SENSOR_ENTITY_DESCRIPTIONS[RAW_SENSOR]
        if coordinator.data.get(sensor_entity.key) or False
    )

    entities.append(
        DerivedUpnpSensor(
            coordinator=coordinator,
            sensor_entity=sensor_entity,
        )
        for sensor_entity in SENSOR_ENTITY_DESCRIPTIONS[DERIVED_SENSOR]
        if coordinator.data.get(sensor_entity.key) or False
    )

    async_add_entities(entities)


class UpnpSensor(UpnpEntity, SensorEntity):
    """Base class for UPnP/IGD sensors."""

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
        sensor_entity: UpnpSensorEntityDescription,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator, sensor_entity)
        self._attr_native_unit_of_measurement = sensor_entity.native_unit_of_measurement
        self._format = sensor_entity.format


class RawUpnpSensor(UpnpSensor):
    """Representation of a UPnP/IGD sensor."""

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        value = self.coordinator.data[self._key]
        if value is None:
            return None
        return format(value, self._format)


class DerivedUpnpSensor(UpnpSensor):
    """Representation of a UNIT Sent/Received per second sensor."""

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
        sensor_entity: UpnpSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator=coordinator, sensor_entity=sensor_entity)
        self._last_value = None
        self._last_timestamp = None

    def _has_overflowed(self, current_value) -> bool:
        """Check if value has overflowed."""
        return current_value < self._last_value

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        # Can't calculate any derivative if we have only one value.
        current_value = self.coordinator.data[self._key]
        if current_value is None:
            return None
        current_timestamp = self.coordinator.data[TIMESTAMP]
        if self._last_value is None or self._has_overflowed(current_value):
            self._last_value = current_value
            self._last_timestamp = current_timestamp
            return None

        # Calculate derivative.
        delta_value = current_value - self._last_value
        if self.native_unit_of_measurement == DATA_BYTES:
            delta_value /= KIBIBYTE
        delta_time = current_timestamp - self._last_timestamp
        if delta_time.total_seconds() == 0:
            # Prevent division by 0.
            return None
        derived = delta_value / delta_time.total_seconds()

        # Store current values for future use.
        self._last_value = current_value
        self._last_timestamp = current_timestamp

        return format(derived, self._format)
