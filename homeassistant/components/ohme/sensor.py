"""Platform for sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ohme import ChargerStatus, OhmeApiClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OhmeConfigEntry
from .entity import OhmeEntity, OhmeEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OhmeSensorDescription(OhmeEntityDescription, SensorEntityDescription):
    """Class describing Ohme sensor entities."""

    value_fn: Callable[[OhmeApiClient], str | int | float | None]


SENSOR_CHARGE_SESSION = [
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
    OhmeSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda client: client.power.volts,
    ),
    OhmeSensorDescription(
        key="battery",
        translation_key="vehicle_battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        suggested_display_precision=0,
        value_fn=lambda client: client.battery,
    ),
    OhmeSensorDescription(
        key="slot_list",
        translation_key="slot_list",
        value_fn=lambda client: ", ".join(str(x) for x in client.slots)
        or STATE_UNKNOWN,
    ),
]

SENSOR_ADVANCED_SETTINGS = [
    OhmeSensorDescription(
        key="ct_current",
        translation_key="ct_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda client: client.power.ct_amps,
        is_supported_fn=lambda client: client.ct_connected,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinators = config_entry.runtime_data
    coordinator_map = [
        (SENSOR_CHARGE_SESSION, coordinators.charge_session_coordinator),
        (SENSOR_ADVANCED_SETTINGS, coordinators.advanced_settings_coordinator),
    ]

    async_add_entities(
        OhmeSensor(coordinator, description)
        for entities, coordinator in coordinator_map
        for description in entities
        if description.is_supported_fn(coordinator.client)
    )


class OhmeSensor(OhmeEntity, SensorEntity):
    """Generic sensor for Ohme."""

    entity_description: OhmeSensorDescription

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.client)
