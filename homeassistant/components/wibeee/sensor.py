"""Wibeee sensor platform for Home Assistant.

Creates sensor entities for each phase and sensor type detected on the
Wibeee energy monitor device. All sensors are ``CoordinatorEntity``
instances backed by a single polling ``WibeeeCoordinator``.

Phases are discovered from the initial data fetch (hardware-dependent).
For each discovered phase, entities are created only for ``SENSOR_TYPES``
whose keys are present in the initial phase data.
"""

from dataclasses import dataclass
import logging
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

from . import WibeeeConfigEntry
from .const import DOMAIN, KNOWN_MODELS
from .coordinator import WibeeeCoordinator

_LOGGER = logging.getLogger(__name__)


PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WibeeeSensorEntityDescription(SensorEntityDescription):
    """Describe a Wibeee sensor entity."""


SENSOR_TYPES: dict[str, WibeeeSensorEntityDescription] = {
    "vrms": WibeeeSensorEntityDescription(
        key="vrms",
        translation_key="phase_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "irms": WibeeeSensorEntityDescription(
        key="irms",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_aparent": WibeeeSensorEntityDescription(
        key="p_aparent",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_activa": WibeeeSensorEntityDescription(
        key="p_activa",
        translation_key="active_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_reactiva_ind": WibeeeSensorEntityDescription(
        key="p_reactiva_ind",
        translation_key="inductive_reactive_power",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_reactiva_cap": WibeeeSensorEntityDescription(
        key="p_reactiva_cap",
        translation_key="capacitive_reactive_power",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "frecuencia": WibeeeSensorEntityDescription(
        key="frecuencia",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "factor_potencia": WibeeeSensorEntityDescription(
        key="factor_potencia",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "energia_activa": WibeeeSensorEntityDescription(
        key="energia_activa",
        translation_key="active_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energia_reactiva_ind": WibeeeSensorEntityDescription(
        key="energia_reactiva_ind",
        translation_key="inductive_reactive_energy",
        native_unit_of_measurement=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energia_reactiva_cap": WibeeeSensorEntityDescription(
        key="energia_reactiva_cap",
        translation_key="capacitive_reactive_energy",
        native_unit_of_measurement=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "angle": WibeeeSensorEntityDescription(
        key="angle",
        translation_key="angle",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_total": WibeeeSensorEntityDescription(
        key="thd_total",
        translation_key="thd_current",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_fund": WibeeeSensorEntityDescription(
        key="thd_fund",
        translation_key="thd_current_fundamental",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar3": WibeeeSensorEntityDescription(
        key="thd_ar3",
        translation_key="thd_current_harmonic_3",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar5": WibeeeSensorEntityDescription(
        key="thd_ar5",
        translation_key="thd_current_harmonic_5",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar7": WibeeeSensorEntityDescription(
        key="thd_ar7",
        translation_key="thd_current_harmonic_7",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar9": WibeeeSensorEntityDescription(
        key="thd_ar9",
        translation_key="thd_current_harmonic_9",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_tot_V": WibeeeSensorEntityDescription(
        key="thd_tot_V",
        translation_key="thd_voltage",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_fun_V": WibeeeSensorEntityDescription(
        key="thd_fun_V",
        translation_key="thd_voltage_fundamental",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar3_V": WibeeeSensorEntityDescription(
        key="thd_ar3_V",
        translation_key="thd_voltage_harmonic_3",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar5_V": WibeeeSensorEntityDescription(
        key="thd_ar5_V",
        translation_key="thd_voltage_harmonic_5",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar7_V": WibeeeSensorEntityDescription(
        key="thd_ar7_V",
        translation_key="thd_voltage_harmonic_7",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar9_V": WibeeeSensorEntityDescription(
        key="thd_ar9_V",
        translation_key="thd_voltage_harmonic_9",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
}

# Map phase names to human-readable labels
PHASE_NAMES: dict[str, str] = {
    "fase1": "L1",
    "fase2": "L2",
    "fase3": "L3",
    "fase4": "Total",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WibeeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wibeee sensor entities from a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    device_info = runtime.device_info

    # Discover phases from initial data (hardware-dependent).
    # Single-phase: fase1 + fase4. Three-phase: fase1-3 + fase4.
    data = coordinator.data
    discovered_phases = [p for p in data if p in PHASE_NAMES]
    if not discovered_phases:
        _LOGGER.warning(
            "No usable phase data for Wibeee %s (%s); no sensors created",
            device_info.mac_addr_short,
            device_info.ip_addr,
        )
        return

    # Build entities: discovered phases x sensor types present in data.
    # Process fase4 (Total) first to ensure the parent device exists.
    sorted_phases = sorted(
        discovered_phases,
        key=lambda p: (0 if p == "fase4" else 1, p),
    )
    entities: list[WibeeeSensor] = [
        WibeeeSensor(
            coordinator=coordinator,
            device_info=device_info,
            phase_key=phase_key,
            description=description,
        )
        for phase_key in sorted_phases
        for sensor_key, description in SENSOR_TYPES.items()
        if sensor_key in data[phase_key]
    ]

    async_add_entities(entities)
    _LOGGER.debug(
        "Added %d sensors for Wibeee %s (%s) across %d phases",
        len(entities),
        device_info.mac_addr_short,
        device_info.ip_addr,
        len(sorted_phases),
    )


# ---------------------------------------------------------------------------
# Device info builder
# ---------------------------------------------------------------------------


def _build_device_info(device_info: WibeeeDeviceInfo, phase_key: str) -> dr.DeviceInfo:
    """Build HA DeviceInfo for a sensor entity."""
    model_name = KNOWN_MODELS.get(device_info.model, f"Wibeee {device_info.model}")
    is_phase = phase_key in ("fase1", "fase2", "fase3")
    phase_label = PHASE_NAMES.get(phase_key, phase_key)

    if is_phase:
        return dr.DeviceInfo(
            identifiers={(DOMAIN, f"{device_info.mac_addr_formatted}_{phase_key}")},
            via_device=(DOMAIN, device_info.mac_addr_formatted),
            name=f"Wibeee {device_info.mac_addr_short} {phase_label}",
            model=f"{model_name} Clamp",
            manufacturer="Smilics",
        )
    return dr.DeviceInfo(
        identifiers={(DOMAIN, device_info.mac_addr_formatted)},
        name=f"Wibeee {device_info.mac_addr_short}",
        model=model_name,
        manufacturer="Smilics",
        sw_version=device_info.firmware_version,
        configuration_url=f"http://{device_info.ip_addr}/",
    )


# ---------------------------------------------------------------------------
# Sensor entity
# ---------------------------------------------------------------------------


class WibeeeSensor(CoordinatorEntity[WibeeeCoordinator], SensorEntity):
    """Wibeee sensor entity backed by the polling coordinator.

    The coordinator provides the data; the sensor reads its specific
    phase/key from it.
    """

    _attr_has_entity_name = True
    entity_description: WibeeeSensorEntityDescription

    def __init__(
        self,
        coordinator: WibeeeCoordinator,
        device_info: WibeeeDeviceInfo,
        phase_key: str,
        description: WibeeeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._phase_key = phase_key
        self.entity_description = description

        self._attr_unique_id = (
            f"{device_info.mac_addr_formatted}_{phase_key}_{description.key}"
        )
        self._attr_translation_key = description.translation_key
        self._attr_device_info = _build_device_info(device_info, phase_key)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the sensor value."""
        value = self.coordinator.data[self._phase_key][self.entity_description.key]
        try:
            return float(value)
        except ValueError, TypeError:
            return None

    @property
    @override
    def available(self) -> bool:
        """Return True if the coordinator has a valid value for this sensor."""
        return super().available and self.native_value is not None
