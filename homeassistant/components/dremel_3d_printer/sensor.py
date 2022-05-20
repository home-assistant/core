"""Support for monitoring Dremel 3D Printer sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Dremel3DPrinterDataUpdateCoordinator, Dremel3DPrinterDeviceEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available Dremel 3D Printer sensors."""
    coordinator: Dremel3DPrinterDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    device_id = config_entry.unique_id

    assert device_id is not None

    entities: list[SensorEntity] = [
        Dremel3DPrinterStatusSensor(coordinator, config_entry),
        Dremel3DPrinterProgressSensor(coordinator, config_entry),
        Dremel3DPrinterTemperatureSensor(coordinator, config_entry, "chamber", False),
        Dremel3DPrinterTemperatureSensor(coordinator, config_entry, "platform"),
        Dremel3DPrinterTemperatureSensor(coordinator, config_entry, "extruder"),
    ]

    async_add_entities(entities)


class Dremel3DPrinterSensorBase(Dremel3DPrinterDeviceEntity, SensorEntity):
    """Representation of an Dremel 3D Printer base sensor."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize a new Dremel 3D Printer base sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = f"{sensor_type}"
        self._attr_unique_id = f"{sensor_type}-{config_entry.unique_id}"


class Dremel3DPrinterStatusSensor(Dremel3DPrinterSensorBase):
    """Representation of a Dremel 3D Printer status sensor."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a new Dremel 3D Printer status sensor."""
        super().__init__(coordinator, config_entry, "Job Phase")

    @property
    def native_value(self) -> str:
        """Return sensor status state."""
        return str(self.coordinator.api.get_printing_status())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return job related attributes for this status sensor."""
        return self.coordinator.api.get_printing_attributes()  # type: ignore[no-any-return]


class Dremel3DPrinterProgressSensor(Dremel3DPrinterSensorBase):
    """Representation of a Dremel 3D Printer progress sensor."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a new Dremel 3D Printer progress sensor."""
        super().__init__(coordinator, config_entry, "Progress")

    @property
    def native_value(self) -> float:
        """Return sensor progress state."""
        return float(self.coordinator.api.get_printing_progress())

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return PERCENTAGE


class Dremel3DPrinterTemperatureSensor(Dremel3DPrinterSensorBase):
    """Representation of a Dremel 3D Printer temperature sensor."""

    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
        temp_type: str,
        has_extra_attrs: bool = True,
    ) -> None:
        """Initialize a new Dremel 3D Printer temperature sensor."""
        super().__init__(
            coordinator, config_entry, temp_type.capitalize() + " Temperature"
        )
        self._temp_type = temp_type
        self._has_extra_attrs = has_extra_attrs

    @property
    def native_value(self) -> int:
        """Return temperature sensor state."""
        return int(self.coordinator.api.get_temperature_type(self._temp_type))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return temperature related attributes for this temperature sensor."""
        if not self._has_extra_attrs:
            return {}
        return self.coordinator.api.get_temperature_attributes(self._temp_type)  # type: ignore[no-any-return]
