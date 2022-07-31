"""Support for IPP sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LOCATION, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_COMMAND_SET,
    ATTR_INFO,
    ATTR_MARKER_HIGH_LEVEL,
    ATTR_MARKER_LOW_LEVEL,
    ATTR_MARKER_TYPE,
    ATTR_SERIAL,
    ATTR_STATE_MESSAGE,
    ATTR_STATE_REASON,
    ATTR_URI_SUPPORTED,
    DOMAIN,
)
from .coordinator import IPPDataUpdateCoordinator
from .entity import IPPEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IPP sensor based on a config entry."""
    coordinator: IPPDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # config flow sets this to either UUID, serial number or None
    if (unique_id := entry.unique_id) is None:
        unique_id = entry.entry_id

    sensors: list[SensorEntity] = []

    sensors.append(IPPPrinterSensor(entry.entry_id, unique_id, coordinator))
    sensors.append(IPPUptimeSensor(entry.entry_id, unique_id, coordinator))

    for marker_index in range(len(coordinator.data.markers)):
        sensors.append(
            IPPMarkerSensor(entry.entry_id, unique_id, coordinator, marker_index)
        )

    async_add_entities(sensors, True)


class IPPSensor(IPPEntity, SensorEntity):
    """Defines an IPP sensor."""

    def __init__(
        self,
        *,
        coordinator: IPPDataUpdateCoordinator,
        enabled_default: bool = True,
        entry_id: str,
        unique_id: str,
        icon: str,
        key: str,
        name: str,
        unit_of_measurement: str | None = None,
    ) -> None:
        """Initialize IPP sensor."""
        self._key = key
        self._attr_unique_id = f"{unique_id}_{key}"
        self._attr_native_unit_of_measurement = unit_of_measurement

        super().__init__(
            entry_id=entry_id,
            device_id=unique_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            enabled_default=enabled_default,
        )


class IPPMarkerSensor(IPPSensor):
    """Defines an IPP marker sensor."""

    def __init__(
        self,
        entry_id: str,
        unique_id: str,
        coordinator: IPPDataUpdateCoordinator,
        marker_index: int,
    ) -> None:
        """Initialize IPP marker sensor."""
        self.marker_index = marker_index

        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            unique_id=unique_id,
            icon="mdi:water",
            key=f"marker_{marker_index}",
            name=f"{coordinator.data.info.name} {coordinator.data.markers[marker_index].name}",
            unit_of_measurement=PERCENTAGE,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        return {
            ATTR_MARKER_HIGH_LEVEL: self.coordinator.data.markers[
                self.marker_index
            ].high_level,
            ATTR_MARKER_LOW_LEVEL: self.coordinator.data.markers[
                self.marker_index
            ].low_level,
            ATTR_MARKER_TYPE: self.coordinator.data.markers[
                self.marker_index
            ].marker_type,
        }

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        level = self.coordinator.data.markers[self.marker_index].level

        if level >= 0:
            return level

        return None


class IPPPrinterSensor(IPPSensor):
    """Defines an IPP printer sensor."""

    def __init__(
        self, entry_id: str, unique_id: str, coordinator: IPPDataUpdateCoordinator
    ) -> None:
        """Initialize IPP printer sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            unique_id=unique_id,
            icon="mdi:printer",
            key="printer",
            name=coordinator.data.info.name,
            unit_of_measurement=None,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        return {
            ATTR_INFO: self.coordinator.data.info.printer_info,
            ATTR_SERIAL: self.coordinator.data.info.serial,
            ATTR_LOCATION: self.coordinator.data.info.location,
            ATTR_STATE_MESSAGE: self.coordinator.data.state.message,
            ATTR_STATE_REASON: self.coordinator.data.state.reasons,
            ATTR_COMMAND_SET: self.coordinator.data.info.command_set,
            ATTR_URI_SUPPORTED: self.coordinator.data.info.printer_uri_supported,
        }

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.state.printer_state


class IPPUptimeSensor(IPPSensor):
    """Defines a IPP uptime sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, entry_id: str, unique_id: str, coordinator: IPPDataUpdateCoordinator
    ) -> None:
        """Initialize IPP uptime sensor."""
        super().__init__(
            coordinator=coordinator,
            enabled_default=False,
            entry_id=entry_id,
            unique_id=unique_id,
            icon="mdi:clock-outline",
            key="uptime",
            name=f"{coordinator.data.info.name} Uptime",
        )

    @property
    def native_value(self) -> datetime:
        """Return the state of the sensor."""
        return utcnow() - timedelta(seconds=self.coordinator.data.info.uptime)
