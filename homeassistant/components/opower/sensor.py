"""Support for Opower sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from opower import Forecast, MeterType, UnitOfMeasure

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpowerCoordinator


@dataclass
class OpowerEntityDescriptionMixin:
    """Mixin values for required keys."""

    value_fn: Callable[[Forecast], str | float]


@dataclass
class OpowerEntityDescription(SensorEntityDescription, OpowerEntityDescriptionMixin):
    """Class describing Opower sensors entities."""


# suggested_display_precision=0 for all sensors since
# Opower provides 0 decimal points for all these.
# (for the statistics in the energy dashboard Opower does provide decimal points)
ELEC_SENSORS: tuple[OpowerEntityDescription, ...] = (
    OpowerEntityDescription(
        key="elec_usage_to_date",
        name="Current bill electric usage to date",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.usage_to_date,
    ),
    OpowerEntityDescription(
        key="elec_forecasted_usage",
        name="Current bill electric forecasted usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecasted_usage,
    ),
    OpowerEntityDescription(
        key="elec_typical_usage",
        name="Typical monthly electric usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.typical_usage,
    ),
    OpowerEntityDescription(
        key="elec_cost_to_date",
        name="Current bill electric cost to date",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        suggested_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.cost_to_date,
    ),
    OpowerEntityDescription(
        key="elec_forecasted_cost",
        name="Current bill electric forecasted cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        suggested_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecasted_cost,
    ),
    OpowerEntityDescription(
        key="elec_typical_cost",
        name="Typical monthly electric cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        suggested_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.typical_cost,
    ),
)
GAS_SENSORS: tuple[OpowerEntityDescription, ...] = (
    OpowerEntityDescription(
        key="gas_usage_to_date",
        name="Current bill gas usage to date",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        suggested_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.usage_to_date,
    ),
    OpowerEntityDescription(
        key="gas_forecasted_usage",
        name="Current bill gas forecasted usage",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        suggested_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecasted_usage,
    ),
    OpowerEntityDescription(
        key="gas_typical_usage",
        name="Typical monthly gas usage",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        suggested_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.typical_usage,
    ),
    OpowerEntityDescription(
        key="gas_cost_to_date",
        name="Current bill gas cost to date",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        suggested_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.cost_to_date,
    ),
    OpowerEntityDescription(
        key="gas_forecasted_cost",
        name="Current bill gas forecasted cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        suggested_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecasted_cost,
    ),
    OpowerEntityDescription(
        key="gas_typical_cost",
        name="Typical monthly gas cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        suggested_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.typical_cost,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Opower sensor."""

    coordinator: OpowerCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[OpowerSensor] = []
    forecasts = coordinator.data.values()
    for forecast in forecasts:
        device_id = f"{coordinator.api.utility.subdomain()}_{forecast.account.utility_account_id}"
        device = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"{forecast.account.meter_type.name} account {forecast.account.utility_account_id}",
            manufacturer="Opower",
            model=coordinator.api.utility.name(),
            entry_type=DeviceEntryType.SERVICE,
        )
        sensors: tuple[OpowerEntityDescription, ...] = ()
        if (
            forecast.account.meter_type == MeterType.ELEC
            and forecast.unit_of_measure == UnitOfMeasure.KWH
        ):
            sensors = ELEC_SENSORS
        elif (
            forecast.account.meter_type == MeterType.GAS
            and forecast.unit_of_measure in [UnitOfMeasure.THERM, UnitOfMeasure.CCF]
        ):
            sensors = GAS_SENSORS
        for sensor in sensors:
            entities.append(
                OpowerSensor(
                    coordinator,
                    sensor,
                    forecast.account.utility_account_id,
                    device,
                    device_id,
                )
            )

    async_add_entities(entities)


class OpowerSensor(CoordinatorEntity[OpowerCoordinator], SensorEntity):
    """Representation of an Opower sensor."""

    entity_description: OpowerEntityDescription

    def __init__(
        self,
        coordinator: OpowerCoordinator,
        description: OpowerEntityDescription,
        utility_account_id: str,
        device: DeviceInfo,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = device
        self.utility_account_id = utility_account_id

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if self.coordinator.data is not None:
            return self.entity_description.value_fn(
                self.coordinator.data[self.utility_account_id]
            )
        return None
