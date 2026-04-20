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

# PTEC (Période Tarifaire en Cours) raw protocol values → clean option keys
PTEC_OPTIONS: dict[str, str] = {
    "TH..": "all_hours",
    "HC..": "off_peak",
    "HP..": "peak",
    "HN..": "normal_hours",
    "PM..": "mobile_peak",
    "HCJB": "off_peak_blue_day",
    "HCJW": "off_peak_white_day",
    "HCJR": "off_peak_red_day",
    "HPJB": "peak_blue_day",
    "HPJW": "peak_white_day",
    "HPJR": "peak_red_day",
}

# DEMAIN (Couleur du lendemain) raw protocol values → clean option keys
DEMAIN_OPTIONS: dict[str, str | None] = {
    "BLEU": "blue",
    "BLAN": "white",
    "ROUG": "red",
    "----": None,
}


@dataclass(frozen=True, kw_only=True)
class TeleinfoSensorEntityDescription(SensorEntityDescription):
    """Describes a Teleinfo sensor entity."""

    value_fn: Callable[[str], StateType] = int


SENSOR_DESCRIPTIONS: tuple[TeleinfoSensorEntityDescription, ...] = (
    # ------------------------------------------------------------------
    # Common sensors (present in all contract types)
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="PAPP",
        translation_key="apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
    ),
    TeleinfoSensorEntityDescription(
        key="IINST",
        translation_key="instantaneous_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
    ),
    TeleinfoSensorEntityDescription(
        key="PTEC",
        translation_key="current_tariff_period",
        device_class=SensorDeviceClass.ENUM,
        options=list(PTEC_OPTIONS.values()),
        value_fn=PTEC_OPTIONS.get,
    ),
    # ------------------------------------------------------------------
    # BASE contract (OPTARIF = "BASE")
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="BASE",
        translation_key="base_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    # ------------------------------------------------------------------
    # HC contract — Heures Creuses (OPTARIF = "HC..")
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="HCHC",
        translation_key="off_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="HCHP",
        translation_key="peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    # ------------------------------------------------------------------
    # EJP contract — Effacement Jours de Pointe (OPTARIF = "EJP.")
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="EJPHN",
        translation_key="normal_hours_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="EJPHPM",
        translation_key="peak_mobile_hours_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="PEJP",
        translation_key="ejp_warning",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_registry_enabled_default=False,
    ),
    # ------------------------------------------------------------------
    # Tempo / BBR contract (OPTARIF = "BBR(" and variants)
    # ------------------------------------------------------------------
    TeleinfoSensorEntityDescription(
        key="BBRHCJB",
        translation_key="blue_day_off_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="BBRHPJB",
        translation_key="blue_day_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="BBRHCJW",
        translation_key="white_day_off_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="BBRHPJW",
        translation_key="white_day_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="BBRHCJR",
        translation_key="red_day_off_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="BBRHPJR",
        translation_key="red_day_peak_index",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    TeleinfoSensorEntityDescription(
        key="DEMAIN",
        translation_key="tomorrow_color",
        device_class=SensorDeviceClass.ENUM,
        options=[v for v in DEMAIN_OPTIONS.values() if v is not None],
        entity_registry_enabled_default=False,
        value_fn=DEMAIN_OPTIONS.get,
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
        if description.key in coordinator.data
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
            super().available and self.entity_description.key in self.coordinator.data
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        data = self.coordinator.data[self.entity_description.key]
        return self.entity_description.value_fn(data)
