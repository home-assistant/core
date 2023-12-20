"""The sensor platform for the A. O. Smith integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AOSmithData
from .const import DOMAIN, HOT_WATER_STATUS_MAP
from .coordinator import AOSmithCoordinator
from .entity import AOSmithEntity


@dataclass(frozen=True, kw_only=True)
class AOSmithSensorEntityDescription(SensorEntityDescription):
    """Define sensor entity description class."""

    value_fn: Callable[[dict[str, Any]], str | int | None]


ENTITY_DESCRIPTIONS: tuple[AOSmithSensorEntityDescription, ...] = (
    AOSmithSensorEntityDescription(
        key="hot_water_availability",
        translation_key="hot_water_availability",
        icon="mdi:water-thermometer",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "medium", "high"],
        value_fn=lambda device: HOT_WATER_STATUS_MAP.get(
            device.get("data", {}).get("hotWaterStatus")
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up A. O. Smith sensor platform."""
    data: AOSmithData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        AOSmithSensorEntity(data.coordinator, description, junction_id)
        for description in ENTITY_DESCRIPTIONS
        for junction_id in data.coordinator.data
    )


class AOSmithSensorEntity(AOSmithEntity, SensorEntity):
    """The sensor entity for the A. O. Smith integration."""

    entity_description: AOSmithSensorEntityDescription

    def __init__(
        self,
        coordinator: AOSmithCoordinator,
        description: AOSmithSensorEntityDescription,
        junction_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, junction_id)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}_{junction_id}"

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)
