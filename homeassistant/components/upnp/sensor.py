"""Support for UPnP/IGD Sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_BYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpnpDataUpdateCoordinator, UpnpEntity
from .const import (
    DERIVED_SENSOR,
    DOMAIN,
    KIBIBYTE,
    LOGGER,
    RAW_SENSOR,
    SENSOR_ENTITY_DESCRIPTIONS,
    TIMESTAMP,
)


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
    )

    entities.append(
        DerivedUpnpSensor(
            coordinator=coordinator,
            sensor_entity=sensor_entity,
        )
        for sensor_entity in SENSOR_ENTITY_DESCRIPTIONS[DERIVED_SENSOR]
    )

    async_add_entities(entities)


class UpnpSensor(UpnpEntity, SensorEntity):
    """Base class for UPnP/IGD sensors."""

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
        sensor_entity: tuple[SensorEntityDescription, str],
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator, sensor_entity[0])
        self._attr_native_unit_of_measurement = sensor_entity[
            0
        ].native_unit_of_measurement
        self._format = sensor_entity[1]


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
        sensor_entity: tuple[SensorEntityDescription, str],
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
