"""Platform for sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ohme import ChargerStatus, OhmeApiClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OhmeConfigEntry, OhmeRuntimeData
from .coordinator import OhmeBaseCoordinator
from .entity import OhmeEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OhmeSensorDescription(SensorEntityDescription):
    """Class describing Ohme sensor entities."""

    value_fn: Callable[[OhmeApiClient], Any]
    is_supported_fn: Callable[[OhmeApiClient], bool] = lambda _: True
    coordinator_fn: Callable[[OhmeRuntimeData], OhmeBaseCoordinator] = (
        lambda data: data.charge_session_coordinator
    )


SENSOR_DESCRIPTIONS = [
    OhmeSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[e.value for e in ChargerStatus],
        value_fn=lambda client: client.status.value,
    ),
    OhmeSensorDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda client: client.power.amps,
    ),
    OhmeSensorDescription(
        key="ct_current",
        translation_key="ct_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda client: client.power.ct_amps,
        is_supported_fn=lambda client: client.ct_connected,
        coordinator_fn=lambda data: data.advanced_settings_coordinator,
    ),
    OhmeSensorDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=1,
        value_fn=lambda client: client.power.watts,
    ),
    OhmeSensorDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda client: client.energy,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinators = config_entry.runtime_data

    async_add_entities(
        OhmeSensor(description.coordinator_fn(coordinators), description)
        for description in SENSOR_DESCRIPTIONS
        if description.is_supported_fn(description.coordinator_fn(coordinators).client)
    )


class OhmeSensor(OhmeEntity, SensorEntity):
    """Generic sensor for Ohme."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.client)
