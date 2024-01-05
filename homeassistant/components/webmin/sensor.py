"""Support for Webmin sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WebminUpdateCoordinator

SENSOR_TYPES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="load_1m",
        translation_key="load_1m",
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="load_5m",
        translation_key="load_5m",
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="load_15m",
        translation_key="load_15m",
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="mem_total",
        translation_key="mem_total",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="mem_free",
        translation_key="mem_free",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="swap_total",
        translation_key="swap_total",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="swap_free",
        translation_key="swap_free",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Webmin sensors based on a config entry."""
    coordinator: WebminUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WebminSensor(coordinator, description)
            for description in SENSOR_TYPES
            if description.key in coordinator.data
        ]
    )


class WebminSensor(CoordinatorEntity[WebminUpdateCoordinator], SensorEntity):
    """Represents a Webmin sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WebminUpdateCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a Webmin sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"

    @property
    def native_value(self) -> int | float:
        """Return the state of the sensor."""
        return self.coordinator.data[self.entity_description.key]
