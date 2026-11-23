"""Support for Daikin AC sensors."""

from dataclasses import dataclass, replace
import logging
from typing import cast, override

from daikin_onecta.models import Characteristic, ManagementPoint, Setpoint

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import Platform, UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ENERGY_AGGREGATE_PERIODS,
    ENTITY_METADATA,
    SENSOR_KEYS,
    entity_description_kwargs,
)
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .discovery import (
    energy_description_key,
    has_settable_climate_setpoint,
    scalar_characteristics_for_platform,
)
from .entity import (
    DaikinManagementPointEntity,
    DaikinOnectaAccountEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    iter_management_points,
    management_point_unique_id,
)
from .utils import enum_value_to_state

PARALLEL_UPDATES = 1
SENSORY_DATA_SENSOR_TYPES = (
    "roomTemperature",
    "outdoorTemperature",
    "leavingWaterTemperature",
    "tankTemperature",
    "roomHumidity",
    "pm1Concentration",
    "pm25Concentration",
    "pm10Concentration",
)
SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    metadata.key: SensorEntityDescription(
        key=metadata.key,
        device_class=cast("SensorDeviceClass | None", metadata.device_class),
        options=list(metadata.options) if metadata.options is not None else None,
        native_unit_of_measurement=metadata.native_unit_of_measurement,
        state_class=metadata.state_class,
        **entity_description_kwargs(metadata),
    )
    for metadata in ENTITY_METADATA
    if metadata.key in SENSOR_KEYS
}

_LOGGER = logging.getLogger(__name__)


def _native_unit(unit: str | None, description: SensorEntityDescription) -> str | None:
    """Return the Daikin unit or the entity-description default."""
    if unit is None:
        return description.native_unit_of_measurement
    try:
        if description.device_class == SensorDeviceClass.ENERGY:
            return UnitOfEnergy(unit)
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            return UnitOfTemperature(unit)
    except ValueError:
        return description.native_unit_of_measurement
    return unit


@dataclass(frozen=True)
class EnergySensorDetails:
    """Parameters that identify an energy sensor."""

    embedded_id: str
    sensor_type: str
    operation_mode: str
    period: str
    datatype: str


@dataclass(frozen=True)
class ValueSensorDetails:
    """Parameters that identify a value sensor."""

    embedded_id: str
    sub_type: str | None
    value: str


def add_energy_sensors(
    coordinator: OnectaDataUpdateCoordinator,
    device: DaikinOnectaDevice,
    management_point: ManagementPoint,
    sensors: list[SensorEntity],
    is_known: EntityIdChecker,
) -> None:
    """Add sensors for every typed energy aggregate exposed by a point."""
    period_order = {
        period: index for index, period in enumerate(ENERGY_AGGREGATE_PERIODS)
    }
    for aggregate in sorted(
        management_point.energy_aggregates,
        key=lambda aggregate: period_order.get(aggregate.period, len(period_order)),
    ):
        description_key = energy_description_key(aggregate)
        if description_key is None:
            _LOGGER.debug(
                "Skipping unsupported Daikin energy aggregate '%s'",
                aggregate,
            )
            continue
        details = EnergySensorDetails(
            management_point.embedded_id,
            aggregate.source,
            aggregate.operation_mode,
            aggregate.period,
            aggregate.data_type,
        )
        unique_id = _energy_sensor_unique_id(device.id, details)
        if is_known(Platform.SENSOR, unique_id):
            continue
        sensors.append(
            DaikinEnergySensor(
                device,
                coordinator,
                SENSOR_DESCRIPTIONS[description_key],
                details,
            )
        )


def add_simple_sensors(
    coordinator: OnectaDataUpdateCoordinator,
    device: DaikinOnectaDevice,
    management_point: ManagementPoint,
    sensors: list[SensorEntity],
    is_known: EntityIdChecker,
) -> None:
    """Add sensors for simple characteristics of one management point."""
    for value, _characteristic in scalar_characteristics_for_platform(
        management_point,
        Platform.SENSOR,
        gateway_online=device.gateway_online,
    ):
        unique_id = _value_sensor_unique_id(
            device.id, management_point.embedded_id, None, value
        )
        if is_known(Platform.SENSOR, unique_id):
            continue
        sensors.append(
            DaikinValueSensor(
                device,
                coordinator,
                SENSOR_DESCRIPTIONS[value],
                ValueSensorDetails(
                    management_point.embedded_id,
                    None,
                    value,
                ),
            )
        )


def add_sensory_sensors(
    coordinator: OnectaDataUpdateCoordinator,
    device: DaikinOnectaDevice,
    management_point: ManagementPoint,
    sensors: list[SensorEntity],
    is_known: EntityIdChecker,
) -> None:
    """Add sensors for sensory data exposed by one management point."""
    sensors.extend(
        DaikinValueSensor(
            device,
            coordinator,
            SENSOR_DESCRIPTIONS[sensor],
            ValueSensorDetails(
                management_point.embedded_id,
                "sensoryData",
                sensor,
            ),
        )
        for sensor in SENSORY_DATA_SENSOR_TYPES
        if sensor in SENSOR_DESCRIPTIONS
        and management_point.sensory_characteristic(sensor) is not None
        and not is_known(
            Platform.SENSOR,
            _value_sensor_unique_id(
                device.id, management_point.embedded_id, "sensoryData", sensor
            ),
        )
    )


def add_management_point_sensors(
    coordinator: OnectaDataUpdateCoordinator,
    device: DaikinOnectaDevice,
    management_point: ManagementPoint,
    sensors: list[SensorEntity],
    is_known: EntityIdChecker,
) -> None:
    """Add all sensors exposed by a management point."""
    add_simple_sensors(coordinator, device, management_point, sensors, is_known)
    add_sensory_sensors(coordinator, device, management_point, sensors, is_known)
    add_read_only_setpoint_sensors(
        device, coordinator, management_point, sensors, is_known
    )
    add_energy_sensors(coordinator, device, management_point, sensors, is_known)


def add_read_only_setpoint_sensors(
    device: DaikinOnectaDevice,
    coordinator: OnectaDataUpdateCoordinator,
    management_point: ManagementPoint,
    sensors: list[SensorEntity],
    is_known: EntityIdChecker,
) -> None:
    """Expose temperature targets that Daikin never allows users to change."""
    climate_control = management_point.climate_control
    if not device.gateway_online or climate_control is None:
        return

    for setpoint_type in climate_control.setpoint_types:
        if setpoint_type not in SENSOR_DESCRIPTIONS or has_settable_climate_setpoint(
            management_point, setpoint_type
        ):
            continue
        if climate_control.setpoint(setpoint_type) is None:
            continue
        unique_id = _value_sensor_unique_id(
            device.id, management_point.embedded_id, "setpoint", setpoint_type
        )
        if is_known(Platform.SENSOR, unique_id):
            continue
        description = SENSOR_DESCRIPTIONS[setpoint_type]
        sensors.append(
            DaikinValueSensor(
                device,
                coordinator,
                replace(
                    description,
                    key=f"{description.key}_setpoint",
                    state_class=None,
                    translation_key=f"{description.translation_key}_setpoint",
                ),
                ValueSensorDetails(
                    management_point.embedded_id,
                    "setpoint",
                    setpoint_type,
                ),
            )
        )


def _energy_sensor_unique_id(device_id: str, details: EnergySensorDetails) -> str:
    """Return the stable unique ID for an energy aggregate."""
    return management_point_unique_id(
        device_id,
        details.embedded_id,
        details.sensor_type,
        details.operation_mode,
        ENERGY_AGGREGATE_PERIODS[details.period].unique_id_suffix,
        details.datatype,
    )


def _value_sensor_unique_id(
    device_id: str, embedded_id: str, sub_type: str | None, value: str
) -> str:
    """Return a stable unique ID for a scalar or sensory-data value."""
    if sub_type == "sensoryData":
        return management_point_unique_id(device_id, embedded_id, "sensory_data", value)
    if sub_type == "setpoint":
        return management_point_unique_id(device_id, embedded_id, "setpoint", value)
    return management_point_unique_id(device_id, embedded_id, value)


def _rate_limit_sensor_unique_id(account_id: str, limit_key: str) -> str:
    """Return a stable unique ID for a rate-limit sensor."""
    return f"{account_id}_rate_limit_{limit_key}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin sensors based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    sensors: list[SensorEntity] = [
        DaikinLimitSensor(
            coordinator,
            SENSOR_DESCRIPTIONS["RatelimitRemainingDay"],
            "remaining_day",
        )
    ]
    async_add_entities(sensors)
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: _create_device_sensors(coordinator, is_known),
    )


def _create_device_sensors(
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[SensorEntity]:
    """Create supported device sensors from the current cloud model."""
    sensors: list[SensorEntity] = []
    for device, management_point in iter_management_points(coordinator):
        add_management_point_sensors(
            coordinator, device, management_point, sensors, is_known
        )
    return sensors


class DaikinEnergySensor(DaikinManagementPointEntity, SensorEntity):
    """Representation of a power/energy sensor."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        description: SensorEntityDescription,
        details: EnergySensorDetails,
    ) -> None:
        """Initialize an energy sensor for a management point."""
        super().__init__(device, coordinator, details.embedded_id)
        self._operation_mode = details.operation_mode
        self._period = details.period
        self._datatype = details.datatype
        self.entity_description = description
        self._sensor_type = details.sensor_type
        self._has_energy_series = False
        self._attr_unique_id = _energy_sensor_unique_id(self._device_id, details)
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        point = self._management_point
        energy_data = (
            point.consumption
            if point is not None and self._datatype == "consumption"
            else point.energy_output
            if point is not None
            else None
        )
        values_period = "month" if self._period == "year" else self._period
        self._has_energy_series = (
            energy_data is not None
            and energy_data.values(
                self._sensor_type, self._operation_mode, values_period
            )
            is not None
        )
        self._attr_native_value = (
            energy_data.current_total(
                self._sensor_type,
                self._operation_mode,
                self._period,
                month=dt_util.now().month if self._period == "month" else None,
            )
            if energy_data is not None
            else None
        )
        source = (
            energy_data.source(self._sensor_type) if energy_data is not None else None
        )
        self._attr_native_unit_of_measurement = _native_unit(
            source.unit if source is not None else None, self.entity_description
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the matching energy aggregate is still available."""
        return super().available and self._has_energy_series


class DaikinValueSensor(DaikinManagementPointEntity, SensorEntity):
    """Represent a Daikin characteristic or sensory-data value."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        description: SensorEntityDescription,
        details: ValueSensorDetails,
    ) -> None:
        """Initialize the sensor from a device value."""
        super().__init__(device, coordinator, details.embedded_id)
        self._sub_type = details.sub_type
        self._value = details.value
        self._unknown_enum_values: set[str] = set()
        self.entity_description = description
        self._attr_unique_id = _value_sensor_unique_id(
            self._device_id,
            details.embedded_id,
            self._sub_type,
            self._value,
        )
        management_point = self._management_point
        if (
            self._value == "errorCode"
            and management_point is not None
            and management_point.management_point_type == "gateway"
        ):
            self._attr_translation_key = "gateway_errorcode"
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        characteristic = self._get_current_characteristic()
        self._is_exposed_on_platform = characteristic is not None and (
            self._sub_type is not None
            or self._characteristic_exposed_on(self._value, Platform.SENSOR)
        )
        self._attr_native_value = self._sensor_value(characteristic)
        self._attr_native_unit_of_measurement = _native_unit(
            characteristic.unit if characteristic is not None else None,
            self.entity_description,
        )

    def _get_current_characteristic(self) -> Characteristic | Setpoint | None:
        """Return the current characteristic from its management point."""
        point = self._management_point
        if point is None:
            return None
        if self._sub_type == "setpoint":
            climate_control = point.climate_control
            return (
                climate_control.setpoint(self._value)
                if climate_control is not None
                else None
            )
        return (
            point.sensory_characteristic(self._value)
            if self._sub_type == "sensoryData"
            else point.characteristic(self._value)
        )

    def _sensor_value(
        self, characteristic: Characteristic | Setpoint | None
    ) -> str | int | float | None:
        """Convert a characteristic value for Home Assistant."""
        result: object = characteristic.value if characteristic is not None else None
        if self._value == "errorCode" and result == "":
            return None
        if (
            isinstance(result, str)
            and self.entity_description.device_class is SensorDeviceClass.ENUM
        ):
            state = enum_value_to_state(result)
            if state not in (self.entity_description.options or []):
                if result not in self._unknown_enum_values:
                    self._unknown_enum_values.add(result)
                    _LOGGER.debug(
                        "Ignoring unsupported Daikin enum value %r for %s",
                        result,
                        self._value,
                    )
                return None
            return state
        return (
            result
            if isinstance(result, str | int | float) and not isinstance(result, bool)
            else None
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the source characteristic is still available."""
        if not super().available:
            return False
        return self._is_exposed_on_platform


class DaikinLimitSensor(DaikinOnectaAccountEntity, SensorEntity):
    """Represent a Daikin API rate-limit value."""

    def __init__(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        description: SensorEntityDescription,
        limit_key: str,
    ) -> None:
        """Initialize a rate-limit sensor."""
        super().__init__(coordinator)
        self._limit_key = limit_key
        self._attr_unique_id = _rate_limit_sensor_unique_id(
            self._account_id, self._limit_key
        )
        self.entity_description = description
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the rate-limit value."""
        self._attr_native_value = self.sensor_value()

    def sensor_value(self) -> int | None:
        """Return the current API rate-limit value."""
        return self.coordinator.rate_limits[self._limit_key]
