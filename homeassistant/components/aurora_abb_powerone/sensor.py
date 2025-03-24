"""Support for Aurora ABB PowerOne Solar Photovoltaic (PV) inverter."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aurorapy.mapping import Mapping as AuroraMapping

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_SERIAL_NUMBER,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import AuroraAbbConfigEntry, AuroraAbbDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
ALARM_STATES = list(AuroraMapping.ALARM_STATES.values())

SENSOR_TYPES = [
    SensorEntityDescription(
        key="grid_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="grid_voltage",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="grid_current",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="grid_current",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="i_leak_dcdc",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="i_leak_dcdc",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="i_leak_inverter",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="i_leak_inverter",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="alarm",
        device_class=SensorDeviceClass.ENUM,
        options=ALARM_STATES,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="alarm",
    ),
    SensorEntityDescription(
        key="instantaneouspower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="power_output",
    ),
    SensorEntityDescription(
        key="temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="r_iso",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="MOhms",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="r_iso",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="totalenergy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="total_energy",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AuroraAbbConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up aurora_abb_powerone sensor based on a config entry."""

    coordinator = config_entry.runtime_data
    data = config_entry.data

    entities = [AuroraSensor(coordinator, data, sens) for sens in SENSOR_TYPES]

    _LOGGER.debug("async_setup_entry adding %d entities", len(entities))
    async_add_entities(entities, True)


class AuroraSensor(CoordinatorEntity[AuroraAbbDataUpdateCoordinator], SensorEntity):
    """Representation of a Sensor on an Aurora ABB PowerOne Solar inverter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AuroraAbbDataUpdateCoordinator,
        data: Mapping[str, Any],
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{data[ATTR_SERIAL_NUMBER]}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data[ATTR_SERIAL_NUMBER])},
            manufacturer=MANUFACTURER,
            model=data[ATTR_MODEL],
            name=data.get(ATTR_DEVICE_NAME, DEFAULT_DEVICE_NAME),
            sw_version=data[ATTR_FIRMWARE],
        )

    @property
    def native_value(self) -> StateType:
        """Get the value of the sensor from previously collected data."""
        return self.coordinator.data.get(self.entity_description.key)
