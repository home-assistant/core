"""Support for voltage, power & energy sensors for VeSync outlets."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from pyvesync.base_devices.fryer_base import FryerState
from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.const import (
    RUNNING_STATUSES,
    AirFryerFeatures,
    AirQualityLevel,
    TemperatureUnits,
    TimeUnits,
)
from pyvesync.device_container import DeviceContainer

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfDensity,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util
from homeassistant.util.variance import ignore_variance

from .common import is_air_fryer, is_humidifier, is_outlet, is_purifier, rgetattr
from .const import AIR_FRYER_MODE_MAP, VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VeSyncSensorEntityDescription(SensorEntityDescription):
    """Describe VeSync sensor entity."""

    exists_fn: Callable[[VeSyncBaseDevice], bool]

    value_fn: Callable[[VeSyncBaseDevice], StateType] | None = None
    state_value_fn: Callable[[FryerState], StateType] | None = None
    use_device_temperature_unit: bool = False
    # The state value is a remaining time in seconds, shown as the time it ends.
    end_time_from_remaining: bool = False


def _get_cook_status(state: FryerState) -> str | None:
    """Return the normalized cook status if available."""
    if state.cook_status is None:
        return None

    cook_status = state.cook_status.lower()
    return AIR_FRYER_MODE_MAP.get(cook_status, cook_status)


def _get_cook_time_remaining(state: FryerState) -> int | None:
    """Return the seconds until the cook finishes, while they count down.

    None when paused or stopped, and in a Sync hold that is not counting down
    yet (no last timestamp), as the end time keeps moving then.
    """
    if state.cook_status not in RUNNING_STATUSES or state.last_timestamp is None:
        return None
    return state.total_time_remaining


def _end_time(remaining: int) -> datetime:
    """Return the time a remaining time in seconds ends."""
    return dt_util.utcnow() + timedelta(seconds=remaining)


# Variance of the end time ignored between updates: the poll time jitters, and
# a fryer reporting minutes steps a whole minute when polled near its boundary.
END_TIME_VARIANCE_SECONDS = timedelta(seconds=5)
END_TIME_VARIANCE_MINUTES = timedelta(seconds=90)


def _get_air_quality(device: VeSyncBaseDevice) -> str | None:
    """Return the air quality level, mapping unknown to None."""
    value = device.state.air_quality_string
    if value == str(AirQualityLevel.UNKNOWN):
        return None
    return value


SENSORS: tuple[VeSyncSensorEntityDescription, ...] = (
    VeSyncSensorEntityDescription(
        key="filter-life",
        translation_key="filter_life",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.filter_life,
        exists_fn=lambda device: rgetattr(device, "state.filter_life") is not None,
    ),
    VeSyncSensorEntityDescription(
        key="air-quality",
        translation_key="air_quality",
        device_class=SensorDeviceClass.ENUM,
        options=["excellent", "good", "moderate", "poor"],
        value_fn=_get_air_quality,
        exists_fn=(
            lambda device: rgetattr(device, "state.air_quality_string") is not None
        ),
    ),
    VeSyncSensorEntityDescription(
        key="pm1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.pm1,
        exists_fn=lambda device: rgetattr(device, "state.pm1") is not None,
    ),
    VeSyncSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.pm10,
        exists_fn=lambda device: rgetattr(device, "state.pm10") is not None,
    ),
    VeSyncSensorEntityDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.pm25,
        exists_fn=lambda device: rgetattr(device, "state.pm25") is not None,
    ),
    VeSyncSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.co2,
        exists_fn=lambda device: is_purifier(device) and device.state.co2 is not None,
    ),
    VeSyncSensorEntityDescription(
        key="power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.power,
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="energy",
        translation_key="energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.state.energy,
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="energy-weekly",
        translation_key="energy_week",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: getattr(
            device.state.weekly_history, "totalEnergy", None
        ),
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="energy-monthly",
        translation_key="energy_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: getattr(
            device.state.monthly_history, "totalEnergy", None
        ),
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="energy-yearly",
        translation_key="energy_year",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: getattr(
            device.state.yearly_history, "totalEnergy", None
        ),
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="voltage",
        translation_key="current_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.voltage,
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.humidity,
        exists_fn=is_humidifier,
    ),
    VeSyncSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.temperature,
        exists_fn=lambda device: (
            is_humidifier(device) and device.state.temperature is not None
        ),
    ),
    VeSyncSensorEntityDescription(
        key="cook_status",
        translation_key="cook_status",
        device_class=SensorDeviceClass.ENUM,
        state_value_fn=_get_cook_status,
        exists_fn=is_air_fryer,
        options=[
            "cooking_end",
            "cooking",
            "cooking_stop",
            "heating",
            "ready",
            "appointing",
            "hold",
            "preheat_end",
            "preheat_stop",
            "pull_out",
            "standby",
        ],
    ),
    VeSyncSensorEntityDescription(
        key="current_temp",
        translation_key="current_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        use_device_temperature_unit=True,
        state_class=SensorStateClass.MEASUREMENT,
        state_value_fn=lambda state: state.current_temp,
        exists_fn=is_air_fryer,
    ),
    VeSyncSensorEntityDescription(
        key="cook_set_temp",
        translation_key="cook_set_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        use_device_temperature_unit=True,
        state_class=SensorStateClass.MEASUREMENT,
        state_value_fn=lambda state: state.cook_set_temp,
        exists_fn=is_air_fryer,
    ),
    VeSyncSensorEntityDescription(
        key="cook_set_time",
        translation_key="cook_set_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_value_fn=lambda state: state.cook_set_time,
        exists_fn=is_air_fryer,
    ),
    VeSyncSensorEntityDescription(
        key="cook_end_time",
        translation_key="cook_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_value_fn=_get_cook_time_remaining,
        end_time_from_remaining=True,
        exists_fn=is_air_fryer,
    ),
    VeSyncSensorEntityDescription(
        key="preheat_set_time",
        translation_key="preheat_set_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_value_fn=lambda state: state.preheat_set_time,
        exists_fn=lambda device: (
            is_air_fryer(device) and AirFryerFeatures.PREHEAT in device.features
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncBaseDevice]) -> None:
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: DeviceContainer | list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Check if device is online and add entity."""

    entities: list[VeSyncSensorEntity] = []
    for device in devices:
        for description in SENSORS:
            if not description.exists_fn(device):
                continue
            if description.state_value_fn is None or not is_air_fryer(device):
                entities.append(VeSyncSensorEntity(device, description, coordinator))
                continue
            entities.append(
                VeSyncSensorEntity(device, description, coordinator, chamber=1)
            )
            if device.is_dual_chamber:
                entities.append(
                    VeSyncSensorEntity(device, description, coordinator, chamber=2)
                )

    async_add_entities(entities, update_before_add=True)


class VeSyncSensorEntity(VeSyncBaseEntity, SensorEntity):
    """Representation of a sensor describing a VeSync device."""

    entity_description: VeSyncSensorEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncSensorEntityDescription,
        coordinator: VeSyncDataCoordinator,
        chamber: int | None = None,
    ) -> None:
        """Initialize the VeSync outlet device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"
        self._fryer_state: FryerState | None = None
        if chamber is not None and is_air_fryer(device):
            self._fryer_state = (
                device.state_chamber_2 if chamber == 2 else device.state_chamber_1
            )
            if device.is_dual_chamber:
                self._attr_translation_key = f"{description.translation_key}_basket"
                self._attr_translation_placeholders = {"basket": str(chamber)}
            if chamber == 2:
                self._attr_unique_id += "-chamber_2"
        self._end_time_variance: timedelta | None = None
        self._get_end_time: Callable[[int], datetime] | None = None
        if description.end_time_from_remaining:
            self._end_time_variance = (
                END_TIME_VARIANCE_SECONDS
                if rgetattr(device, "time_units") == TimeUnits.SECONDS
                else END_TIME_VARIANCE_MINUTES
            )

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        if self.entity_description.state_value_fn is not None:
            if self._fryer_state is None:
                return None
            value = self.entity_description.state_value_fn(self._fryer_state)
            if self._end_time_variance is None:
                return value
            if value is None:
                # Paused, stopped or done: the next cook starts from a fresh end time.
                self._get_end_time = None
                return None
            if self._get_end_time is None:
                self._get_end_time = ignore_variance(_end_time, self._end_time_variance)
            return self._get_end_time(int(value))
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.device)

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value was reported in by the sensor."""
        if self.entity_description.use_device_temperature_unit:
            if self.device.temp_unit == TemperatureUnits.CELSIUS:
                return UnitOfTemperature.CELSIUS
            if self.device.temp_unit == TemperatureUnits.FAHRENHEIT:
                return UnitOfTemperature.FAHRENHEIT
        return super().native_unit_of_measurement
