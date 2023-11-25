"""Support for Aurora ABB PowerOne Solar Photovoltaic (PV) inverter."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AuroraAbbDataUpdateCoordinator
from .const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = [
    SensorEntityDescription(
        key="alarm",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="alarm",
    ),
    SensorEntityDescription(
        key="boostertemp",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="booster_temp",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="dcdcleak",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        translation_key="dcdc_leak",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="gridvoltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        translation_key="grid_voltage",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="instantaneouspower",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="power_output",
    ),
    SensorEntityDescription(
        key="inverterleak",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        translation_key="inverter_leak",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="invertertemp",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="inverter_temp",
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
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up aurora_abb_powerone sensor based on a config entry."""
    entities = []

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    data = config_entry.data

    for sens in SENSOR_TYPES:
        entities.append(AuroraSensor(coordinator, data, sens))

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
