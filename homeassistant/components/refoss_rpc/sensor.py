"""Sensor entities for Refoss."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import RefossConfigEntry, RefossCoordinator
from .entity import (
    RefossAttributeEntity,
    RefossEntityDescription,
    async_setup_entry_refoss,
)
from .utils import get_device_uptime, is_refoss_wifi_stations_disabled


@dataclass(frozen=True, kw_only=True)
class RefossSensorDescription(RefossEntityDescription, SensorEntityDescription):
    """Class to describe a sensor."""


REFOSS_SENSORS: Final = {
    "power": RefossSensorDescription(
        key="switch",
        sub_key="apower",
        name="Power",
        native_unit_of_measurement=UnitOfPower.MILLIWATT,
        value=lambda status, _: None if status is None else float(status),
        suggested_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "voltage": RefossSensorDescription(
        key="switch",
        sub_key="voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value=lambda status, _: None if status is None else float(status),
        suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "current": RefossSensorDescription(
        key="switch",
        sub_key="current",
        name="Current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        value=lambda status, _: None if status is None else float(status),
        suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "energy": RefossSensorDescription(
        key="switch",
        sub_key="month_consumption",
        name="This Month Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value=lambda status, _: None if status is None else float(status),
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "temperature": RefossSensorDescription(
        key="sys",
        sub_key="temperature",
        name="Device temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda status, _: status["tc"],
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_polling_coordinator=True,
    ),
    "rssi": RefossSensorDescription(
        key="wifi",
        sub_key="rssi",
        name="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        removal_condition=is_refoss_wifi_stations_disabled,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_polling_coordinator=True,
    ),
    "uptime": RefossSensorDescription(
        key="sys",
        sub_key="uptime",
        name="Uptime",
        value=get_device_uptime,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        use_polling_coordinator=True,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RefossConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    coordinator = config_entry.runtime_data.coordinator
    assert coordinator

    async_setup_entry_refoss(
        hass, config_entry, async_add_entities, REFOSS_SENSORS, RefossSensor
    )


class RefossSensor(RefossAttributeEntity, SensorEntity):
    """Refoss sensor entity."""

    entity_description: RefossSensorDescription

    def __init__(
        self,
        coordinator: RefossCoordinator,
        key: str,
        attribute: str,
        description: RefossSensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, key, attribute, description)

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.attribute_value
