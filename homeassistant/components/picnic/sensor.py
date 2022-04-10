"""Definition of Picnic sensors."""
from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ADDRESS,
    ATTRIBUTION,
    CONF_COORDINATOR,
    DOMAIN,
    SENSOR_TYPES,
    PicnicSensorEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Picnic sensor entries."""
    picnic_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    # Add an entity for each sensor type
    async_add_entities(
        PicnicSensor(picnic_coordinator, config_entry, description)
        for description in SENSOR_TYPES
    )


class PicnicSensor(SensorEntity, CoordinatorEntity):
    """The CoordinatorEntity subclass representing Picnic sensors."""

    _attr_attribution = ATTRIBUTION
    entity_description: PicnicSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        config_entry: ConfigEntry,
        description: PicnicSensorEntityDescription,
    ) -> None:
        """Init a Picnic sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self.entity_id = f"sensor.picnic_{description.key}"
        self._service_unique_id = config_entry.unique_id

        self._attr_name = self._to_capitalized_name(description.key)
        self._attr_unique_id = f"{config_entry.unique_id}.{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        data_set = (
            self.coordinator.data.get(self.entity_description.data_type, {})
            if self.coordinator.data is not None
            else {}
        )
        return self.entity_description.value_fn(data_set)

    @property
    def available(self) -> bool:
        """Return True if last update was successful."""
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, cast(str, self._service_unique_id))},
            manufacturer="Picnic",
            model=self._service_unique_id,
            name=f"Picnic: {self.coordinator.data[ADDRESS]}",
        )

    @staticmethod
    def _to_capitalized_name(name: str) -> str:
        return name.replace("_", " ").capitalize()
