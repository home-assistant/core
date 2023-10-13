"""Sensor platform for Acaia."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, OUNCES, UNITS
from .entity import AcaiaEntity, AcaiaEntityDescription


@dataclass
class AcaiaSensorEntityDescriptionMixin:
    """Mixin for Acaia Sensor entities."""

    unit_fn: Callable[[dict[str, Any]], str] | None


@dataclass
class AcaiaSensorEntityDescription(
    SensorEntityDescription, AcaiaEntityDescription, AcaiaSensorEntityDescriptionMixin
):
    """Description for Acaia Sensor entities."""


SENSORS: tuple[AcaiaSensorEntityDescription, ...] = (
    AcaiaSensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery",
        unique_id_fn=lambda scale: f"{scale.mac}_battery",
        unit_fn=None,
    ),
    AcaiaSensorEntityDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement="g",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale",
        unique_id_fn=lambda scale: f"{scale.mac}_weight",
        unit_fn=lambda data: "oz" if data.get(UNITS) == OUNCES else "g",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities and services."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [AcaiaSensor(coordinator, entity_description) for entity_description in SENSORS]
    )


class AcaiaSensor(AcaiaEntity, RestoreSensor):
    """Representation of a Acaia Sensor."""

    entity_description: AcaiaSensorEntityDescription

    def __init__(self, coordinator, entity_description) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

        self._native_unit_of_measurement = entity_description.native_unit_of_measurement
        self._data: dict[str, Any] = {}
        self._restored: bool = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._data = self.coordinator.data
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._data[self.entity_description.key] = last_sensor_data.native_value
            self._native_unit_of_measurement = (
                last_sensor_data.native_unit_of_measurement
            )
            self._restored = True

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        if not self._restored and self.entity_description.unit_fn is not None:
            self.entity_description.unit_fn(self._data)
        return self._native_unit_of_measurement

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._data.get(self.entity_description.key, 0)
