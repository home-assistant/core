"""Sensor platform for the APsystems Lake_6 integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import LAKE6_BATTERY_STATUS_TO_STATE
from .coordinator import Lake6ConfigEntry, Lake6Coordinator
from .entity import Lake6Entity


@dataclass(frozen=True, kw_only=True)
class Lake6SensorEntityDescription(SensorEntityDescription):
    """Describes a Lake_6 sensor.

    `value_fn` takes the coordinator instead of `Lake6Data`: the two `/devices`
    fields (capacity, signal) live on `coordinator.device` and are not part of a
    refresh cycle (§5.1).
    """

    value_fn: Callable[[Lake6Coordinator], StateType]


SENSORS: tuple[Lake6SensorEntityDescription, ...] = (
    Lake6SensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda c: c.data.energies.battery_soc,
    ),
    Lake6SensorEntityDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda c: c.data.energies.battery_temperature,
    ),
    Lake6SensorEntityDescription(
        key="device_temperature",
        translation_key="device_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.energies.device_temperature,
    ),
    Lake6SensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        # The sign direction is undocumented, so the raw value is passed through
        # without negation.
        value_fn=lambda c: c.data.energies.battery_power,
    ),
    Lake6SensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.energies.grid_power,
    ),
    Lake6SensorEntityDescription(
        key="offgrid_power",
        translation_key="offgrid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.energies.offgrid_power,
    ),
    Lake6SensorEntityDescription(
        key="battery_charge_energy",
        translation_key="battery_charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=4,
        value_fn=lambda c: c.data.energies.battery_charge_energy,
    ),
    Lake6SensorEntityDescription(
        key="battery_discharge_energy",
        translation_key="battery_discharge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=4,
        value_fn=lambda c: c.data.energies.battery_discharge_energy,
    ),
    Lake6SensorEntityDescription(
        key="grid_import_energy",
        translation_key="grid_import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=4,
        value_fn=lambda c: c.data.energies.grid_import_energy,
    ),
    Lake6SensorEntityDescription(
        key="grid_export_energy",
        translation_key="grid_export_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=4,
        value_fn=lambda c: c.data.energies.grid_export_energy,
    ),
    Lake6SensorEntityDescription(
        key="offgrid_import_energy",
        translation_key="offgrid_import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=4,
        value_fn=lambda c: c.data.energies.offgrid_import_energy,
    ),
    Lake6SensorEntityDescription(
        key="offgrid_export_energy",
        translation_key="offgrid_export_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=4,
        value_fn=lambda c: c.data.energies.offgrid_export_energy,
    ),
    Lake6SensorEntityDescription(
        key="battery_status",
        translation_key="battery_status",
        device_class=SensorDeviceClass.ENUM,
        # Read straight from the mapping table, so a new firmware state only
        # needs a const.py change.
        options=list(LAKE6_BATTERY_STATUS_TO_STATE.values()),
        value_fn=lambda c: c.data.energies.battery_status,
    ),
    Lake6SensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.device.battery_capacity,
    ),
    Lake6SensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.device.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Lake6ConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lake_6 sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    add_entities(Lake6SensorEntity(coordinator, description) for description in SENSORS)


class Lake6SensorEntity(Lake6Entity, SensorEntity):
    """A sensor backed by a single Lake_6 API field."""

    entity_description: Lake6SensorEntityDescription

    def __init__(
        self,
        coordinator: Lake6Coordinator,
        entity_description: Lake6SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self.device_id}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator)
