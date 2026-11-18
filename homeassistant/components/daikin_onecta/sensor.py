"""Support for Daikin AC sensors."""

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, override

from daikin_onecta.models import Characteristic, EnergyAggregate, ManagementPoint

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
    SENSOR_PERIOD_UNIQUE_IDS,
    SENSORY_DATA_SENSOR_TYPES,
)
from .coordinator import DaikinOnectaConfigEntry
from .device import DaikinOnectaDevice
from .discovery import (
    energy_description_key,
    scalar_characteristics_for_platform,
    scalar_platform,
)
from .entity import (
    DaikinManagementPointEntity,
    DaikinOnectaAccountEntity,
    add_entities_on_coordinator_update,
    management_point_unique_id,
)
from .entity_metadata import ENTITY_METADATA, SENSOR_KEYS, entity_description_kwargs
from .utils import enum_value_to_state

PARALLEL_UPDATES = 1

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    metadata.key: SensorEntityDescription(
        key=metadata.key,
        device_class=metadata.device_class,
        options=list(metadata.options) if metadata.options is not None else None,
        native_unit_of_measurement=metadata.native_unit_of_measurement,
        state_class=metadata.state_class,
        **entity_description_kwargs(metadata),
    )
    for metadata in ENTITY_METADATA
    if metadata.key in SENSOR_KEYS
}

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator

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
        return unit
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
    added_unique_ids: set[str],
) -> None:
    """Add sensors for every typed energy aggregate exposed by a point."""
    supported_aggregates = []
    for aggregate in management_point.energy_aggregates:
        if aggregate.period not in ENERGY_AGGREGATE_PERIODS:
            _LOGGER.debug(
                "Skipping unsupported Daikin energy period '%s'", aggregate.period
            )
            continue
        supported_aggregates.append(aggregate)

    for aggregate in sorted(
        supported_aggregates,
        key=lambda aggregate: tuple(ENERGY_AGGREGATE_PERIODS).index(aggregate.period),
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
        if unique_id in added_unique_ids:
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
    added_unique_ids: set[str],
) -> None:
    """Add sensors for simple characteristics of one management point."""
    for value, _characteristic in scalar_characteristics_for_platform(
        management_point, Platform.SENSOR
    ):
        unique_id = _value_sensor_unique_id(
            device.id, management_point.embedded_id, None, value
        )
        if unique_id in added_unique_ids:
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
    added_unique_ids: set[str],
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
        and _value_sensor_unique_id(
            device.id, management_point.embedded_id, "sensoryData", sensor
        )
        not in added_unique_ids
    )


def add_management_point_sensors(
    coordinator: OnectaDataUpdateCoordinator,
    device: DaikinOnectaDevice,
    management_point: ManagementPoint,
    sensors: list[SensorEntity],
    added_unique_ids: set[str],
) -> None:
    """Add all sensors exposed by a management point."""
    add_simple_sensors(coordinator, device, management_point, sensors, added_unique_ids)
    add_sensory_sensors(
        coordinator, device, management_point, sensors, added_unique_ids
    )
    add_energy_sensors(coordinator, device, management_point, sensors, added_unique_ids)


def _energy_sensor_unique_id(device_id: str, details: EnergySensorDetails) -> str:
    """Return the stable unique ID for an energy aggregate."""
    return management_point_unique_id(
        device_id,
        details.embedded_id,
        details.sensor_type,
        details.operation_mode,
        SENSOR_PERIOD_UNIQUE_IDS[ENERGY_AGGREGATE_PERIODS[details.period]],
        details.datatype,
    )


def _value_sensor_unique_id(
    device_id: str, embedded_id: str, sub_type: str | None, value: str
) -> str:
    """Return a stable unique ID for a scalar or sensory-data value."""
    if sub_type == "sensoryData":
        return management_point_unique_id(device_id, embedded_id, "sensory_data", value)
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
        config_entry,
        coordinator,
        async_add_entities,
        lambda added: _create_device_sensors(coordinator, added),
    )


def _create_device_sensors(
    coordinator: OnectaDataUpdateCoordinator,
    added_unique_ids: set[str],
) -> list[SensorEntity]:
    """Create supported device sensors from the current cloud model."""
    sensors: list[SensorEntity] = []
    for device in (coordinator.data or {}).values():
        for management_point in device.device.management_points:
            add_management_point_sensors(
                coordinator, device, management_point, sensors, added_unique_ids
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
        self._attr_unique_id = _energy_sensor_unique_id(self._device.id, details)
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        self._attr_native_value = self.sensor_value()
        point = self._device.management_point(self._embedded_id)
        energy_data = None
        if point is not None:
            energy_data = (
                point.consumption
                if self._datatype == "consumption"
                else point.energy_output
            )
        source = (
            energy_data.source(self._sensor_type) if energy_data is not None else None
        )
        self._attr_native_unit_of_measurement = _native_unit(
            source.unit if source is not None else None, self.entity_description
        )

    def _energy_aggregate(self) -> EnergyAggregate | None:
        """Return the matching energy aggregate from the current model."""
        point = self._device.management_point(self._embedded_id)
        if point is None:
            return None
        period = self._period
        return next(
            (
                aggregate
                for aggregate in point.energy_aggregates
                if aggregate.data_type == self._datatype
                and aggregate.source == self._sensor_type
                and aggregate.operation_mode == self._operation_mode
                and aggregate.period == period
            ),
            None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the matching energy aggregate is still available."""
        return super().available and self._energy_aggregate() is not None

    def sensor_value(self) -> float | None:
        """Return energy aggregated for the current day, week, month, or year.

        Daikin returns rolling windows for each aggregation period. The first
        half of the daily, weekly, and yearly arrays represents the preceding
        period; the second half represents the current period. Consequently,
        the current day starts at ``d[12]``, the current week at ``w[7]``,
        and the current year at ``m[12]``. The current month is a single slot
        in the monthly array.

        Daikin publishes consumption data on its own schedule. ``None`` means
        that a time slot is not available yet and contributes no consumption
        until a later update supplies its value.
        """
        period = self._period
        aggregate = self._energy_aggregate()
        if aggregate is None:
            return None
        return aggregate.current_total(
            month=dt_util.now().month if period == "month" else None
        )


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
            self._device.id,
            details.embedded_id,
            self._sub_type,
            self._value,
        )
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        _, characteristic = self._current_characteristic()
        self._attr_native_value = self._sensor_value(characteristic)
        self._attr_native_unit_of_measurement = _native_unit(
            characteristic.unit if characteristic is not None else None,
            self.entity_description,
        )

    def _current_characteristic(
        self,
    ) -> tuple[ManagementPoint | None, Characteristic | None]:
        """Return the current characteristic from its management point."""
        point = self._device.management_point(self._embedded_id)
        if point is None:
            return None, None
        characteristic = (
            point.sensory_characteristic(self._value)
            if self._sub_type == "sensoryData"
            else point.scalar_characteristic(self._value)
        )
        return point, characteristic

    def sensor_value(self) -> str | int | float | None:
        """Return a typed characteristic or sensory value."""
        _, characteristic = self._current_characteristic()
        return self._sensor_value(characteristic)

    def _sensor_value(
        self, characteristic: Characteristic | None
    ) -> str | int | float | None:
        """Convert a characteristic value for Home Assistant."""
        result: object = characteristic.value if characteristic is not None else None
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
        return result if isinstance(result, str | int | float) else None

    @property
    @override
    def available(self) -> bool:
        """Return whether the source characteristic is still available."""
        if not super().available:
            return False
        point, characteristic = self._current_characteristic()
        return (
            point is not None
            and characteristic is not None
            and (
                self._sub_type is not None
                or scalar_platform(
                    self._value, characteristic, point.management_point_type
                )
                is Platform.SENSOR
            )
        )


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
