"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from ultraheat_api.response import HeatMeterResponse

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from . import DOMAIN
from .const import GJ_IDENTITY_KEY, GJ_ONLY_KEYS, MWH_IDENTITY_KEY, MWH_ONLY_KEYS

_LOGGER = logging.getLogger(__name__)


@dataclass
class HeatMeterSensorEntityDescription(SensorEntityDescription):
    """Heat Meter sensor description."""

    value_fn: Callable | None = None
    response_key: str | None = None


HEAT_METER_SENSOR_TYPES = (
    HeatMeterSensorEntityDescription(
        key="heat_usage",
        icon="mdi:fire",
        name="Heat usage",
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda value: value,
        response_key="heat_usage_mwh",
    ),
    HeatMeterSensorEntityDescription(
        key="volume_usage_m3",
        icon="mdi:fire",
        name="Volume usage",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda value: value,
        response_key="volume_usage_m3",
    ),
    HeatMeterSensorEntityDescription(
        key="heat_usage_gj",
        icon="mdi:fire",
        name="Heat usage GJ",
        native_unit_of_measurement=UnitOfEnergy.GIGA_JOULE,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda value: value,
        response_key="heat_usage_gj",
    ),
    HeatMeterSensorEntityDescription(
        key="heat_previous_year",
        icon="mdi:fire",
        name="Heat previous year",
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="heat_previous_year_mwh",
    ),
    HeatMeterSensorEntityDescription(
        key="heat_previous_year_gj",
        icon="mdi:fire",
        name="Heat previous year GJ",
        native_unit_of_measurement=UnitOfEnergy.GIGA_JOULE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="heat_previous_year_gj",
    ),
    HeatMeterSensorEntityDescription(
        key="volume_previous_year_m3",
        icon="mdi:fire",
        name="Volume usage previous year",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="volume_previous_year_m3",
    ),
    HeatMeterSensorEntityDescription(
        key="ownership_number",
        name="Ownership number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="ownership_number",
    ),
    HeatMeterSensorEntityDescription(
        key="error_number",
        name="Error number",
        icon="mdi:home-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="error_number",
    ),
    HeatMeterSensorEntityDescription(
        key="device_number",
        name="Device number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="device_number",
    ),
    HeatMeterSensorEntityDescription(
        key="measurement_period_minutes",
        name="Measurement period minutes",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="measurement_period_minutes",
    ),
    HeatMeterSensorEntityDescription(
        key="power_max_kw",
        name="Power max",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="power_max_kw",
    ),
    HeatMeterSensorEntityDescription(
        key="power_max_previous_year_kw",
        name="Power max previous year",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="power_max_previous_year_kw",
    ),
    HeatMeterSensorEntityDescription(
        key="flowrate_max_m3ph",
        name="Flowrate max",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:water-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="flowrate_max_m3ph",
    ),
    HeatMeterSensorEntityDescription(
        key="flowrate_max_previous_year_m3ph",
        name="Flowrate max previous year",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:water-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="flowrate_max_previous_year_m3ph",
    ),
    HeatMeterSensorEntityDescription(
        key="return_temperature_max_c",
        name="Return temperature max",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="return_temperature_max_c",
    ),
    HeatMeterSensorEntityDescription(
        key="return_temperature_max_previous_year_c",
        name="Return temperature max previous year",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="return_temperature_max_previous_year_c",
    ),
    HeatMeterSensorEntityDescription(
        key="flow_temperature_max_c",
        name="Flow temperature max",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="flow_temperature_max_c",
    ),
    HeatMeterSensorEntityDescription(
        key="flow_temperature_max_previous_year_c",
        name="Flow temperature max previous year",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="flow_temperature_max_previous_year_c",
    ),
    HeatMeterSensorEntityDescription(
        key="operating_hours",
        name="Operating hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="operating_hours",
    ),
    HeatMeterSensorEntityDescription(
        key="flow_hours",
        name="Flow hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="flow_hours",
    ),
    HeatMeterSensorEntityDescription(
        key="fault_hours",
        name="Fault hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="fault_hours",
    ),
    HeatMeterSensorEntityDescription(
        key="fault_hours_previous_year",
        name="Fault hours previous year",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="fault_hours_previous_year",
    ),
    HeatMeterSensorEntityDescription(
        key="yearly_set_day",
        name="Yearly set day",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="yearly_set_day",
    ),
    HeatMeterSensorEntityDescription(
        key="monthly_set_day",
        name="Monthly set day",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="monthly_set_day",
    ),
    HeatMeterSensorEntityDescription(
        key="meter_date_time",
        name="Meter date time",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=dt_util.as_utc,
        response_key="meter_date_time",
    ),
    HeatMeterSensorEntityDescription(
        key="measuring_range_m3ph",
        name="Measuring range",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:water-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="measuring_range_m3ph",
    ),
    HeatMeterSensorEntityDescription(
        key="settings_and_firmware",
        name="Settings and firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value,
        response_key="settings_and_firmware",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    unique_id = entry.entry_id
    coordinator: DataUpdateCoordinator[HeatMeterResponse] = hass.data[DOMAIN][
        entry.entry_id
    ]

    model = entry.data["model"]

    device = DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer="Landis & Gyr",
        model=model,
        name="Landis+Gyr Heat Meter",
    )

    energy_unit = energy_unit_from_data(coordinator.data)
    if energy_unit == UnitOfEnergy.GIGA_JOULE:
        exclude_keys = MWH_ONLY_KEYS
    elif energy_unit == UnitOfEnergy.MEGA_WATT_HOUR:
        exclude_keys = GJ_ONLY_KEYS
    else:
        exclude_keys = set()

    sensors = []
    for description in HEAT_METER_SENSOR_TYPES:
        if description.key not in exclude_keys:
            sensors.append(HeatMeterSensor(coordinator, description, device))

    async_add_entities(sensors)


class HeatMeterSensor(
    CoordinatorEntity[DataUpdateCoordinator[HeatMeterResponse]], SensorEntity
):
    """Representation of a Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[HeatMeterResponse],
        description: SensorEntityDescription,
        device: DeviceInfo,
    ) -> None:
        """Set up the sensor with the initial values."""
        super().__init__(coordinator)
        self.key = description.key
        self._attr_unique_id = f"{coordinator.config_entry.data['device_number']}_{description.key}"  # type: ignore[union-attr]
        self._attr_name = f"Heat Meter {description.name}"
        self.entity_description = description

        self._attr_device_info = device

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(  # type: ignore[attr-defined]
            getattr(self.coordinator.data, self.entity_description.response_key, None)  # type: ignore[attr-defined]
        )


def energy_unit_from_data(data) -> str | None:
    """Determine the energy unit of measurement (MWh or GJ) this device uses."""
    if data:
        mwh_supplied = getattr(data, MWH_IDENTITY_KEY, None)
        gj_supplied = getattr(data, GJ_IDENTITY_KEY, None)

        if mwh_supplied and not gj_supplied:
            # MWh is returned and GJ not: remove GJ entities
            return UnitOfEnergy.MEGA_WATT_HOUR

        if gj_supplied and not mwh_supplied:
            # GJ is returned and MWH not: remove MWH entities
            return UnitOfEnergy.GIGA_JOULE

    return None
