"""Support for Wibeee energy monitor sensors."""

from typing import override

from pywibeee import WibeeeDeviceInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KNOWN_MODELS, PHASE_LABELS
from .coordinator import WibeeeConfigEntry, WibeeeCoordinator

PARALLEL_UPDATES = 0


SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "vrms": SensorEntityDescription(
        key="vrms",
        translation_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "irms": SensorEntityDescription(
        key="irms",
        translation_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_aparent": SensorEntityDescription(
        key="p_aparent",
        translation_key="apparent_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_activa": SensorEntityDescription(
        key="p_activa",
        translation_key="active_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_reactiva_ind": SensorEntityDescription(
        key="p_reactiva_ind",
        translation_key="inductive_reactive_power",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_reactiva_cap": SensorEntityDescription(
        key="p_reactiva_cap",
        translation_key="capacitive_reactive_power",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "frecuencia": SensorEntityDescription(
        key="frecuencia",
        translation_key="frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "factor_potencia": SensorEntityDescription(
        key="factor_potencia",
        translation_key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "energia_activa": SensorEntityDescription(
        key="energia_activa",
        translation_key="active_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Newer firmware (4.x) reports the cumulative counters in separate
    # consumed/produced keys and leaves energia_activa at 0.
    "energia_activa_cons": SensorEntityDescription(
        key="energia_activa_cons",
        translation_key="consumed_active_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energia_activa_prod": SensorEntityDescription(
        key="energia_activa_prod",
        translation_key="produced_active_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energia_reactiva_ind": SensorEntityDescription(
        key="energia_reactiva_ind",
        translation_key="inductive_reactive_energy",
        native_unit_of_measurement=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energia_reactiva_cap": SensorEntityDescription(
        key="energia_reactiva_cap",
        translation_key="capacitive_reactive_energy",
        native_unit_of_measurement=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "angle": SensorEntityDescription(
        key="angle",
        translation_key="phase_angle",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        entity_registry_enabled_default=False,
    ),
    "thd_total": SensorEntityDescription(
        key="thd_total",
        translation_key="thd_current",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_fund": SensorEntityDescription(
        key="thd_fund",
        translation_key="thd_current_fundamental",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar3": SensorEntityDescription(
        key="thd_ar3",
        translation_key="thd_current_harmonic",
        translation_placeholders={"order": "3"},
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar5": SensorEntityDescription(
        key="thd_ar5",
        translation_key="thd_current_harmonic",
        translation_placeholders={"order": "5"},
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar7": SensorEntityDescription(
        key="thd_ar7",
        translation_key="thd_current_harmonic",
        translation_placeholders={"order": "7"},
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar9": SensorEntityDescription(
        key="thd_ar9",
        translation_key="thd_current_harmonic",
        translation_placeholders={"order": "9"},
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_tot_V": SensorEntityDescription(
        key="thd_tot_V",
        translation_key="thd_voltage",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_fun_V": SensorEntityDescription(
        key="thd_fun_V",
        translation_key="thd_voltage_fundamental",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar3_V": SensorEntityDescription(
        key="thd_ar3_V",
        translation_key="thd_voltage_harmonic",
        translation_placeholders={"order": "3"},
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar5_V": SensorEntityDescription(
        key="thd_ar5_V",
        translation_key="thd_voltage_harmonic",
        translation_placeholders={"order": "5"},
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar7_V": SensorEntityDescription(
        key="thd_ar7_V",
        translation_key="thd_voltage_harmonic",
        translation_placeholders={"order": "7"},
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar9_V": SensorEntityDescription(
        key="thd_ar9_V",
        translation_key="thd_voltage_harmonic",
        translation_placeholders={"order": "9"},
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WibeeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wibeee sensor entities from a config entry."""
    coordinator = entry.runtime_data
    device_info = coordinator.device_info

    # The coordinator guarantees data only contains known phases.
    data = coordinator.data
    async_add_entities(
        WibeeeSensor(
            coordinator=coordinator,
            device_info=device_info,
            phase_key=phase_key,
            description=description,
        )
        for phase_key in data
        for sensor_key, description in SENSOR_TYPES.items()
        if sensor_key in data[phase_key]
        # 4.x firmware leaves the legacy aggregate at 0 next to the split
        # consumed/produced counters; don't expose a dead energy sensor.
        and (
            sensor_key != "energia_activa"
            or "energia_activa_cons" not in data[phase_key]
        )
    )


def _build_device_info(device_info: WibeeeDeviceInfo) -> dr.DeviceInfo:
    """Build HA DeviceInfo for the Wibeee device."""
    return dr.DeviceInfo(
        identifiers={(DOMAIN, device_info.mac_addr_formatted)},
        name=f"Wibeee {device_info.mac_addr_short}",
        model=KNOWN_MODELS.get(device_info.model, f"Wibeee {device_info.model}"),
        manufacturer="Smilics",
        sw_version=device_info.firmware_version,
        configuration_url=f"http://{device_info.ip_addr}/",
    )


class WibeeeSensor(CoordinatorEntity[WibeeeCoordinator], SensorEntity):
    """Wibeee sensor entity backed by the polling coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WibeeeCoordinator,
        device_info: WibeeeDeviceInfo,
        phase_key: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._phase_key = phase_key
        self.entity_description = description

        self._attr_unique_id = (
            f"{device_info.mac_addr_formatted}_{phase_key}_{description.key}"
        )
        self._attr_device_info = _build_device_info(device_info)
        self._attr_translation_placeholders = {
            "phase": PHASE_LABELS[phase_key],
            **(description.translation_placeholders or {}),
        }

    @property
    @override
    def native_value(self) -> float | None:
        """Return the sensor value."""
        value = self.coordinator.data[self._phase_key][self.entity_description.key]
        if value is None:
            return None
        return float(value)

    @property
    @override
    def available(self) -> bool:
        """Return True if the phase data contains this sensor's key."""
        return (
            super().available
            and self._phase_key in self.coordinator.data
            and self.entity_description.key in self.coordinator.data[self._phase_key]
        )
