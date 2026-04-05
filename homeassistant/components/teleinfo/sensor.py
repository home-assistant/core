"""Sensor platform for the Teleinfo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TeleinfoConfigEntry, TeleinfoCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeleinfoSensorEntityDescription(SensorEntityDescription):
    """Describes a Teleinfo sensor entity."""

    value_fn: Callable[[dict[str, str]], StateType]
    required_label: str


SENSOR_DESCRIPTIONS: tuple[TeleinfoSensorEntityDescription, ...] = (
    # ------------------------------------------------------------------
    # Common sensors (present in all contract types)
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="apparent_power",
        translation_key="apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        required_label="PAPP",
        value_fn=lambda data: int(data["PAPP"]),
    ),
    TeleinfoSensorEntityDescription(
        key="instantaneous_current",
        translation_key="instantaneous_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        required_label="IINST",
        value_fn=lambda data: int(data["IINST"]),
    ),
    TeleinfoSensorEntityDescription(
        key="current_tariff_period",
        translation_key="current_tariff_period",
        required_label="PTEC",
        value_fn=lambda data: data["PTEC"],
    ),
    # ------------------------------------------------------------------
    # BASE contract (OPTARIF = "BASE")
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="base_index",
        translation_key="base_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="BASE",
        value_fn=lambda data: int(data["BASE"]),
    ),
    # ------------------------------------------------------------------
    # HC contract — Heures Creuses (OPTARIF = "HC..")
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="off_peak_index",
        translation_key="off_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="HCHC",
        value_fn=lambda data: int(data["HCHC"]),
    ),
    TeleinfoSensorEntityDescription(
        key="peak_index",
        translation_key="peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="HCHP",
        value_fn=lambda data: int(data["HCHP"]),
    ),
    # ------------------------------------------------------------------
    # EJP contract — Effacement Jours de Pointe (OPTARIF = "EJP.")
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="normal_hours_index",
        translation_key="normal_hours_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="EJPHN",
        value_fn=lambda data: int(data["EJPHN"]),
    ),
    TeleinfoSensorEntityDescription(
        key="peak_mobile_hours_index",
        translation_key="peak_mobile_hours_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="EJPHPM",
        value_fn=lambda data: int(data["EJPHPM"]),
    ),
    TeleinfoSensorEntityDescription(
        key="ejp_warning",
        translation_key="ejp_warning",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_registry_enabled_default=False,
        required_label="PEJP",
        value_fn=lambda data: int(data["PEJP"]),
    ),
    # ------------------------------------------------------------------
    # Tempo / BBR contract (OPTARIF = "BBR(" and variants)
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="blue_day_off_peak_index",
        translation_key="blue_day_off_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="BBRHCJB",
        value_fn=lambda data: int(data["BBRHCJB"]),
    ),
    TeleinfoSensorEntityDescription(
        key="blue_day_peak_index",
        translation_key="blue_day_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="BBRHPJB",
        value_fn=lambda data: int(data["BBRHPJB"]),
    ),
    TeleinfoSensorEntityDescription(
        key="white_day_off_peak_index",
        translation_key="white_day_off_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="BBRHCJW",
        value_fn=lambda data: int(data["BBRHCJW"]),
    ),
    TeleinfoSensorEntityDescription(
        key="white_day_peak_index",
        translation_key="white_day_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="BBRHPJW",
        value_fn=lambda data: int(data["BBRHPJW"]),
    ),
    TeleinfoSensorEntityDescription(
        key="red_day_off_peak_index",
        translation_key="red_day_off_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="BBRHCJR",
        value_fn=lambda data: int(data["BBRHCJR"]),
    ),
    TeleinfoSensorEntityDescription(
        key="red_day_peak_index",
        translation_key="red_day_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        required_label="BBRHPJR",
        value_fn=lambda data: int(data["BBRHPJR"]),
    ),
    TeleinfoSensorEntityDescription(
        key="tomorrow_color",
        translation_key="tomorrow_color",
        entity_registry_enabled_default=False,
        required_label="DEMAIN",
        value_fn=lambda data: data["DEMAIN"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeleinfoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Teleinfo sensor entities."""
    coordinator = entry.runtime_data
    adco = coordinator.data["ADCO"]

    async_add_entities(
        TeleinfoSensor(coordinator, description, adco)
        for description in SENSOR_DESCRIPTIONS
        if description.required_label in coordinator.data
    )


class TeleinfoSensor(CoordinatorEntity[TeleinfoCoordinator], SensorEntity):
    """Representation of a Teleinfo sensor entity."""

    _attr_has_entity_name = True
    entity_description: TeleinfoSensorEntityDescription

    def __init__(
        self,
        coordinator: TeleinfoCoordinator,
        description: TeleinfoSensorEntityDescription,
        adco: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{adco}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, adco)},
            name=f"Teleinfo {adco}",
            manufacturer="Enedis",
        )

    @property
    def available(self) -> bool:
        """Return True if the required label is present in the frame."""
        return (
            super().available
            and self.entity_description.required_label in self.coordinator.data
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
