"""nVent RAYCHEM SENZ sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pysenz import Thermostat

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SENZConfigEntry, SENZDataUpdateCoordinator
from .const import DOMAIN


@dataclass(kw_only=True, frozen=True)
class SenzSensorDescription(SensorEntityDescription):
    """Describes SENZ sensor entity."""

    value_fn: Callable[[Thermostat], str | int | float | None]


SENSORS: tuple[SenzSensorDescription, ...] = (
    SenzSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda data: data.current_temperatue,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SENZConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SENZ sensor entities from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        SENZSensor(thermostat, coordinator, description)
        for description in SENSORS
        for thermostat in coordinator.data.values()
    )


class SENZSensor(CoordinatorEntity[SENZDataUpdateCoordinator], SensorEntity):
    """Representation of a SENZ sensor entity."""

    entity_description: SenzSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        thermostat: Thermostat,
        coordinator: SENZDataUpdateCoordinator,
        description: SenzSensorDescription,
    ) -> None:
        """Init SENZ sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._thermostat = thermostat
        self._attr_unique_id = f"{thermostat.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, thermostat.serial_number)},
            manufacturer="nVent Raychem",
            model="SENZ WIFI",
            name=thermostat.name,
            serial_number=thermostat.serial_number,
        )

    @property
    def available(self) -> bool:
        """Return True if the thermostat is available."""
        return super().available and self._thermostat.online

    @property
    def native_value(self) -> str | float | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._thermostat)
