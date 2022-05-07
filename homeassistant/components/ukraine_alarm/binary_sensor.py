"""binary sensors for Ukraine Alarm integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UkraineAlarmDataUpdateCoordinator
from .const import ATTRIBUTION, BINARY_SENSOR_TYPES, DEFAULT_NAME, DOMAIN, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ukraine Alarm binary sensor entities based on a config entry."""
    name = config_entry.data[CONF_NAME]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        UkraineAlarmSensor(
            name,
            config_entry.unique_id,
            description,
            coordinator,
        )
        for description in BINARY_SENSOR_TYPES
    )


class UkraineAlarmSensor(CoordinatorEntity, BinarySensorEntity):
    """Class for a Ukraine Alarm binary sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        name,
        unique_id,
        description: BinarySensorEntityDescription,
        coordinator: UkraineAlarmDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{unique_id}-{description.key}".lower()
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            name=DEFAULT_NAME,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.get(self.entity_description.key, None)
