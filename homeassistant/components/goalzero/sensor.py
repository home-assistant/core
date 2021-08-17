"""Support for Goal Zero Yeti Sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import Yeti, YetiEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Goal Zero Yeti sensor."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        YetiSensor(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            description,
            entry.entry_id,
        )
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


class YetiSensor(YetiEntity, SensorEntity):
    """Representation of a Goal Zero Yeti sensor."""

    def __init__(
        self,
        api: Yeti,
        coordinator: DataUpdateCoordinator,
        name: str,
        description: SensorEntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize a Goal Zero Yeti sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self._attr_name = f"{name} {description.name}"
        self.entity_description = description
        self._attr_unique_id = f"{server_unique_id}/{description.key}"

    @property
    def native_value(self) -> str:
        """Return the state."""
        return self.api.data.get(self.entity_description.key)
