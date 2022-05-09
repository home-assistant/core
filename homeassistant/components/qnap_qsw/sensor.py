"""Support for the QNAP QSW sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from aioqsw.const import (
    QSD_FAN1_SPEED,
    QSD_FAN2_SPEED,
    QSD_SYSTEM_SENSOR,
    QSD_SYSTEM_TIME,
    QSD_TEMP,
    QSD_TEMP_MAX,
    QSD_UPTIME,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TIME_SECONDS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MAX, DOMAIN, RPM
from .coordinator import QswUpdateCoordinator
from .entity import QswEntityDescription, QswSensorEntity


@dataclass
class QswSensorEntityDescription(SensorEntityDescription, QswEntityDescription):
    """A class that describes QNAP QSW sensor entities."""

    attributes: dict[str, list[str]] | None = None


SENSOR_TYPES: Final[tuple[QswSensorEntityDescription, ...]] = (
    QswSensorEntityDescription(
        icon="mdi:fan-speed-1",
        key=QSD_SYSTEM_SENSOR,
        name="Fan 1 Speed",
        native_unit_of_measurement=RPM,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_FAN1_SPEED,
    ),
    QswSensorEntityDescription(
        icon="mdi:fan-speed-2",
        key=QSD_SYSTEM_SENSOR,
        name="Fan 2 Speed",
        native_unit_of_measurement=RPM,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_FAN2_SPEED,
    ),
    QswSensorEntityDescription(
        attributes={
            ATTR_MAX: [QSD_SYSTEM_SENSOR, QSD_TEMP_MAX],
        },
        device_class=SensorDeviceClass.TEMPERATURE,
        key=QSD_SYSTEM_SENSOR,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        subkey=QSD_TEMP,
    ),
    QswSensorEntityDescription(
        icon="mdi:timer-outline",
        key=QSD_SYSTEM_TIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Uptime",
        native_unit_of_measurement=TIME_SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        subkey=QSD_UPTIME,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add QNAP QSW sensors from a config_entry."""
    coordinator: QswUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        QswSensor(coordinator, description, entry)
        for description in SENSOR_TYPES
        if (
            description.key in coordinator.data
            and description.subkey in coordinator.data[description.key]
        )
    )


class QswSensor(QswSensorEntity, SensorEntity):
    """Define a QNAP QSW sensor."""

    entity_description: QswSensorEntityDescription

    def __init__(
        self,
        coordinator: QswUpdateCoordinator,
        description: QswSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_name = f"{self.product} {description.name}"
        self._attr_unique_id = (
            f"{entry.unique_id}_{description.key}_{description.subkey}"
        )
        self.entity_description = description
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = self.get_device_value(
            self.entity_description.key, self.entity_description.subkey
        )
        super()._async_update_attrs()
