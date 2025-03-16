"""A sensor for the current Rointe radiator temperature."""

from __future__ import annotations

from datetime import datetime

from rointesdk.device import RointeDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import RointeDataUpdateCoordinator, RointeSensorEntityDescription
from .entity import RointeRadiatorEntity


def _get_energy_last_reset(radiator) -> datetime | None:
    """Get energy cycle last reset date."""
    if radiator.energy_data:
        return radiator.energy_data.start

    return None


def _get_energy_consumption(radiator) -> float | None:
    """Return device's consumption."""
    if radiator.energy_data:
        return radiator.energy_data.kwh

    return None


def _get_effective_power(radiator) -> float | None:
    """Return device's effective power."""
    if radiator.energy_data:
        return radiator.energy_data.effective_power

    return None


SENSOR_DESCRIPTIONS = [
    # Current room temperature sensor (probe value).
    RointeSensorEntityDescription(
        key="current_temperature",
        name_fn=lambda radiator: f"{radiator.name} Current Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda radiator: radiator.temp_probe,
        last_reset_fn=lambda radiator: None,
    ),
    # Energy usage in Kw/h.
    RointeSensorEntityDescription(
        key="energy_consumption",
        name_fn=lambda radiator: f"{radiator.name} Energy Consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_energy_consumption,
        last_reset_fn=_get_energy_last_reset,
    ),
    # Effective power usage in W.
    RointeSensorEntityDescription(
        key="power",
        name_fn=lambda radiator: f"{radiator.name} Effective Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_effective_power,
        last_reset_fn=lambda radiator: None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the radiator sensors from the config entry."""
    coordinator: RointeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    coordinator.add_sensor_entities_for_seen_keys(
        async_add_entities, SENSOR_DESCRIPTIONS, RointeGenericSensor
    )


class RointeGenericSensor(RointeRadiatorEntity, SensorEntity):
    """Generic radiator sensor."""

    entity_description: RointeSensorEntityDescription

    def __init__(
        self,
        radiator: RointeDevice,
        coordinator: RointeDataUpdateCoordinator,
        description: RointeSensorEntityDescription,
    ) -> None:
        """Initialize a generic sensor."""
        super().__init__(
            coordinator,
            radiator,
            unique_id=f"{radiator.id}-{description.key}",
        )

        self.entity_description = description

    @property
    def name(self) -> str:
        """Return the entity's name."""
        return self.entity_description.name_fn(self._radiator)

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._radiator)

    @property
    def last_reset(self) -> datetime | None:
        """Return the last time the sensor was initialized, if relevant."""
        return self.entity_description.last_reset_fn(self._radiator)
