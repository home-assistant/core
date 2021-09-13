"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_RATE_MEBIBYTES_PER_SECOND,
    DATA_RATE_MEGABITS_PER_SECOND,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BboxCoordinator, BboxData
from .const import DOMAIN

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="current_down_bandwidth",
        name="Download speed",
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        icon="mdi:download-network",
    ),
    SensorEntityDescription(
        key="current_up_bandwidth",
        name="Upload speed",
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        icon="mdi:upload-network",
    ),
    SensorEntityDescription(
        key="number_of_reboots",
        name="Number of reboot",
        icon="mdi:restart",
    ),
)

SENSOR_UPTIME: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="uptime",
        name="Uptime",
        icon="mdi:clock",
    ),
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Bbox sensor."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=config,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Bbox entities from a config_entry."""
    coordinator: BboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [BboxSensor(coordinator, descr) for descr in SENSORS]

    async_add_entities(entities)


class BboxSensor(CoordinatorEntity[BboxData], SensorEntity):
    """Representation of a Sensor."""

    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._description = description
        self.entity_description = description
        self._attr_name = f"{self.coordinator.name} {self._description.name}"
        self._sensor_value = None
        self._attr_unique_id = f"{coordinator.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self.coordinator.data["device_info"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.data.get(self._description.key) is not None
        )

    @staticmethod
    def units_convert(value, unit) -> StateType:
        """Convert value to correct units."""
        if unit == DATA_RATE_MEGABITS_PER_SECOND:
            return round(float(value) / 1000, 3)
        if unit == DATA_RATE_MEBIBYTES_PER_SECOND:
            return round(float(value) / 1024 / 8, 3)
        return value

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return self.units_convert(
            self.coordinator.data.get(self._description.key),
            self._description.native_unit_of_measurement,
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._description.native_unit_of_measurement or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        attributes = {}
        max_key = f"{self._description.key}_max"
        if max_key in self.coordinator.data:
            attributes["maximum"] = self.units_convert(
                self.coordinator.data.get(max_key),
                self._description.native_unit_of_measurement,
            )

        return attributes
