"""Support for Goal Zero Yeti Sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_POWER,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import Yeti, YetiEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN

PARALLEL_UPDATES = 0

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="backlight",
        name="Backlight",
        icon="mdi:clock-digital",
    ),
    BinarySensorEntityDescription(
        key="app_online",
        name="App Online",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="isCharging",
        name="Charging",
        device_class=DEVICE_CLASS_BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key="inputDetected",
        name="Input Detected",
        device_class=DEVICE_CLASS_POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Goal Zero Yeti sensor."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        YetiBinarySensor(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            description,
            entry.entry_id,
        )
        for description in BINARY_SENSOR_TYPES
    )


class YetiBinarySensor(YetiEntity, BinarySensorEntity):
    """Representation of a Goal Zero Yeti sensor."""

    def __init__(
        self,
        api: Yeti,
        coordinator: DataUpdateCoordinator,
        name: str,
        description: BinarySensorEntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize a Goal Zero Yeti sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{server_unique_id}/{description.key}"

    @property
    def is_on(self) -> bool:
        """Return if the service is on."""
        return self.api.data.get(self.entity_description.key) == 1
