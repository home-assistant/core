"""Sensors for the sunsynk web api."""

from collections.abc import Callable
from dataclasses import dataclass
import decimal
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SunsynkConfigEntry
from .const import DOMAIN
from .coordinator import SunsynkUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SunsynkEntitySensorDescription(SensorEntityDescription):
    """A small wrapper for describing sunsynk entity sensors."""

    agg_func: Callable = sum


SENSOR_DESCRIPTIONS = [
    SunsynkEntitySensorDescription(  # ""A gauge for battery power."""
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key="battery_power",
        translation_key="battery_power",
    ),
    SunsynkEntitySensorDescription(  # A gauge for the load on all inverters."
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key="load_power",
        translation_key="load_power",
    ),
    SunsynkEntitySensorDescription(  # ""A gauge for the load to or from the grid."""
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key="grid_power",
        translation_key="grid_power",
    ),
    SunsynkEntitySensorDescription(  # ""A gauge for the power from generator (typically solar panels)."""
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        key="pv_power",
        translation_key="pv_power",
    ),
    SunsynkEntitySensorDescription(  # ""A gauge to track batter charge."""
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        key="state_of_charge",
        translation_key="state_of_charge",
        agg_func=max,
    ),
    SunsynkEntitySensorDescription(  # ""Accumulated energy generated (typically by solar panels)."""
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key="acc_pv",
        translation_key="acc_pv",
        suggested_display_precision=2,
    ),
    SunsynkEntitySensorDescription(  # ""Total energy consumed through the inverters."""
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key="acc_load",
        translation_key="acc_load",
        suggested_display_precision=2,
    ),
    SunsynkEntitySensorDescription(  # ""Total energy imported from the grid."""
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key="acc_grid_import",
        translation_key="acc_grid_import",
        suggested_display_precision=2,
        agg_func=max,
    ),
    SunsynkEntitySensorDescription(  # ""Total energy exported to the grid."""
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key="acc_grid_export",
        translation_key="acc_grid_export",
        suggested_display_precision=2,
        agg_func=max,
    ),
    SunsynkEntitySensorDescription(  # ""Total energy injected into the batteries."""
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key="acc_battery_charge",
        translation_key="acc_battery_charge",
        suggested_display_precision=2,
    ),
    SunsynkEntitySensorDescription(  # ""Total energy provided by the batteries."""
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        key="acc_battery_discharge",
        translation_key="acc_battery_discharge",
        suggested_display_precision=2,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunsynkConfigEntry,
    async_add_entities: AddEntitiesCallback,  # noqa: F821
) -> None:
    """Set up sensor devices."""
    coordinator: SunsynkUpdateCoordinator = entry.runtime_data

    async_add_entities(
        SunSynkApiSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SunSynkApiSensor(CoordinatorEntity[SunsynkUpdateCoordinator], SensorEntity):
    """Parent class for sunsynk api exposing sensors.

    The sensors expose the sum of the power across all inverters
    for plants that have more than one inverter.
    State of charge is normally shared between inverters, so this will take
    the maximum of the state of charge.
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator, description: SunsynkEntitySensorDescription
    ) -> None:
        """Initialise the common elements for sunsynk web api sensors."""
        CoordinatorEntity.__init__(self, coordinator, context=coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = (
            f"{description.key}_{sum(p.id for p in coordinator.cache.plants)}"
        )
        self.entity_id = f"sensor.sunsynk_{description.key}"

        self.entity_description: SunsynkEntitySensorDescription = description
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, str(sum(plant.id for plant in self.coordinator.cache.plants))),
            },
            name="sunsynk_installation",
            manufacturer="Sunsynk",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.cache is not None:
            self.native_value = self.entity_description.agg_func(
                decimal.Decimal(getattr(i, self.entity_description.key))
                for i in self.coordinator.cache.plants
            )
        else:
            _LOGGER.debug("Not updating sensor as coordinator cache is empty. ")
        self.async_write_ha_state()
