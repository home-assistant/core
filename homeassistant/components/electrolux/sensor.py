"""Sensor entity for Electrolux Integration."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance
from electrolux_group_developer_sdk.constants import APPLIANCE_STATE_RUNNING
from electrolux_group_developer_sdk.feature_constants import (
    APPLIANCE_STATE,
    DISPLAY_FOOD_PROBE_TEMPERATURE_C,
    DISPLAY_FOOD_PROBE_TEMPERATURE_F,
    DISPLAY_TEMPERATURE_C,
    DISPLAY_TEMPERATURE_F,
    FOOD_PROBE_STATE,
    REMOTE_CONTROL,
    RUNNING_TIME,
    START_TIME,
    STOP_TIME,
    TIME_TO_END,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import ELECTROLUX_TO_HA_TEMPERATURE_UNIT
from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import (
    convert_to_snake_case,
    get_submodule_entity_key,
    get_submodule_translation_key,
    round_to_minute,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ElectroluxSensorDescription[T: ApplianceData](SensorEntityDescription):
    """Custom sensor description for Electrolux sensors."""

    exists_fn: Callable[[T], bool] = lambda appliance: True
    value_fn: Callable[[T], StateType | datetime]


@dataclass(frozen=True, kw_only=True)
class ElectroluxEnumSensorDescription[T: ApplianceData](ElectroluxSensorDescription[T]):
    """Custom sensor description for Electrolux sensors."""

    feature_name: str
    known_values: set[str]
    device_class = SensorDeviceClass.ENUM


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleSensorDescription[T: ApplianceData](SensorEntityDescription):
    """Custom sensor description for Electrolux appliance submodule sensors."""

    exists_fn: Callable[[T, str], bool] = lambda appliance, submodule: True
    value_fn: Callable[[T, str], StateType | datetime]


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleEnumSensorDescription[T: ApplianceData](
    ElectroluxSubmoduleSensorDescription[T]
):
    """Custom sensor description for Electrolux appliance submodule sensors."""

    feature_name: str
    known_values: set[str]
    device_class = SensorDeviceClass.ENUM


@dataclass(frozen=True, kw_only=True)
class ElectroluxTemperatureSensorDescription[T: ApplianceData](SensorEntityDescription):
    """Custom sensor description for Electrolux temperature sensors."""

    exists_fn: Callable[[T], bool] = lambda appliance: True
    value_fn: Callable[[T, UnitOfTemperature], float | None]


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleTemperatureSensorDescription[T: ApplianceData](
    SensorEntityDescription
):
    """Custom sensor description for Electrolux temperature sensors."""

    exists_fn: Callable[[T, str], bool] = lambda appliance, submodule: True
    value_fn: Callable[[T, str, UnitOfTemperature], float | None]


def get_oven_start_at(appliance: OVAppliance) -> datetime | None:
    """Get when the appliance will start."""
    return (
        round_to_minute(start_at)
        if (start_at := appliance.get_current_start_at()) is not None
        else None
    )


def get_oven_running_time(appliance: OVAppliance) -> float | None:
    """Get the amount of time the oven has been running for."""
    running_time = appliance.get_current_running_time()
    if running_time is None or running_time <= 0:
        return None
    return running_time


def get_oven_time_left(appliance: OVAppliance) -> float | None:
    """Get the amount of time left the oven will be running for."""
    time_to_end = appliance.get_current_time_to_end()
    if time_to_end is None or time_to_end <= 0:
        return None
    return time_to_end


OVEN_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription[OVAppliance], ...] = (
    ElectroluxEnumSensorDescription[OVAppliance](
        key="appliance_state",
        translation_key="appliance_state",
        value_fn=lambda appliance: appliance.get_current_appliance_state(),
        device_class=SensorDeviceClass.ENUM,
        feature_name=APPLIANCE_STATE,
        exists_fn=lambda appliance: appliance.is_feature_supported(APPLIANCE_STATE),
        known_values={
            "alarm",
            "delayed_start",
            "end_of_cycle",
            "idle",
            "off",
            "paused",
            "ready_to_start",
            "running",
        },
    ),
    ElectroluxEnumSensorDescription(
        key="food_probe_state",
        translation_key="food_probe_state",
        value_fn=lambda appliance: appliance.get_current_food_probe_insertion_state(),
        device_class=SensorDeviceClass.ENUM,
        feature_name=FOOD_PROBE_STATE,
        exists_fn=lambda appliance: appliance.is_feature_supported(FOOD_PROBE_STATE),
        known_values={
            "inserted",
            "not_inserted",
        },
    ),
    ElectroluxEnumSensorDescription(
        key="remote_control",
        translation_key="remote_control",
        value_fn=lambda appliance: appliance.get_current_remote_control(),
        device_class=SensorDeviceClass.ENUM,
        feature_name=REMOTE_CONTROL,
        exists_fn=lambda appliance: appliance.is_feature_supported(REMOTE_CONTROL),
        known_values={
            "disabled",
            "enabled",
            "not_safety_relevant_enabled",
            "temporary_locked",
        },
    ),
    ElectroluxSensorDescription(
        key="start_at",
        translation_key="start_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        exists_fn=lambda appliance: appliance.is_feature_supported(START_TIME),
        value_fn=get_oven_start_at,
    ),
    ElectroluxSensorDescription(
        key="running_time",
        translation_key="running_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda appliance: appliance.is_feature_supported(RUNNING_TIME),
        value_fn=get_oven_running_time,
    ),
    ElectroluxSensorDescription(
        key="time_left",
        translation_key="time_left",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda appliance: appliance.is_feature_supported(TIME_TO_END),
        value_fn=get_oven_time_left,
    ),
)

OVEN_TEMPERATURE_ELECTROLUX_SENSORS: tuple[
    ElectroluxTemperatureSensorDescription[OVAppliance], ...
] = (
    ElectroluxTemperatureSensorDescription(
        key="food_probe_temperature",
        translation_key="food_probe_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda appliance, temp_unit: (
            appliance.get_current_display_food_probe_temperature_f()
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_display_food_probe_temperature_c()
        ),
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_FOOD_PROBE_TEMPERATURE_F, DISPLAY_FOOD_PROBE_TEMPERATURE_C]
        ),
    ),
    ElectroluxTemperatureSensorDescription(
        key="display_temperature",
        translation_key="display_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda appliance, temp_unit: (
            appliance.get_current_display_temperature_f()
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_display_temperature_c()
        ),
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_TEMPERATURE_C, DISPLAY_TEMPERATURE_F]
        ),
    ),
)


def get_structured_oven_start_at(
    appliance: SOAppliance, cavity: str
) -> datetime | None:
    """Get when the appliance will start."""
    return (
        round_to_minute(start_at)
        if (start_at := appliance.get_current_cavity_start_at(cavity)) is not None
        else None
    )


def get_structured_oven_running_time(
    appliance: SOAppliance, cavity: str
) -> float | None:
    """Get the amount of time the oven has been running for."""
    running_time = appliance.get_current_cavity_running_time(cavity)
    if running_time is None or running_time <= 0:
        return None
    return running_time


def get_structured_oven_time_left(appliance: SOAppliance, cavity: str) -> float | None:
    """Get the amount of time left the oven will be running for."""
    time_to_end = appliance.get_current_cavity_time_to_end(cavity)
    if time_to_end is None or time_to_end <= 0:
        return None
    return time_to_end


STRUCTURED_OVEN_CAVITY_ELECTROLUX_SENSORS: tuple[
    ElectroluxSubmoduleSensorDescription[SOAppliance], ...
] = (
    ElectroluxSubmoduleSensorDescription(
        key="start_at",
        translation_key="start_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, START_TIME
        ),
        value_fn=get_structured_oven_start_at,
    ),
    ElectroluxSubmoduleSensorDescription(
        key="running_time",
        translation_key="running_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, RUNNING_TIME
        ),
        value_fn=get_structured_oven_running_time,
    ),
    ElectroluxSubmoduleSensorDescription(
        key="time_left",
        translation_key="time_left",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, TIME_TO_END
        ),
        value_fn=get_structured_oven_time_left,
    ),
)


def get_care_appliance_start_at(
    appliance: DWAppliance | TDAppliance | WDAppliance | WMAppliance,
) -> datetime | None:
    """Get when the appliance will start."""
    return (
        round_to_minute(start_at)
        if (start_at := appliance.get_current_start_at()) is not None
        else None
    )


def get_care_appliance_end_at(
    appliance: DWAppliance | TDAppliance | WDAppliance | WMAppliance,
) -> datetime | None:
    """Get when the appliance will stop running."""
    end_at: datetime | None = appliance.get_current_end_at()
    if end_at is not None:
        return round_to_minute(end_at)

    if appliance.get_current_appliance_state() is not APPLIANCE_STATE_RUNNING:
        return None

    time_to_end = appliance.get_current_time_to_end()
    if time_to_end is None or time_to_end <= 0:
        return None
    end_at = utcnow() + timedelta(seconds=time_to_end)
    return round_to_minute(end_at)


def get_care_appliance_time_left(
    appliance: DWAppliance | TDAppliance | WDAppliance | WMAppliance,
) -> float | None:
    """Get the amount of time left the appliance will be running for."""
    time_to_end = appliance.get_current_time_to_end()
    if time_to_end is None or time_to_end <= 0:
        return None
    return time_to_end


CARE_ELECTROLUX_SENSORS: tuple[
    ElectroluxSensorDescription[DWAppliance | TDAppliance | WDAppliance | WMAppliance],
    ...,
] = (
    ElectroluxSensorDescription(
        key="start_at",
        translation_key="start_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [START_TIME, STOP_TIME]
        ),
        value_fn=get_care_appliance_start_at,
    ),
    ElectroluxSensorDescription(
        key="end_at",
        translation_key="end_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [START_TIME, STOP_TIME]
        ),
        value_fn=get_care_appliance_end_at,
    ),
    ElectroluxSensorDescription(
        key="time_left",
        translation_key="time_left",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda appliance: appliance.is_feature_supported(TIME_TO_END),
        value_fn=get_care_appliance_time_left,
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, OVAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in OVEN_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

        entities.extend(
            ElectroluxTemperatureSensor(appliance_data, coordinator, description)
            for description in OVEN_TEMPERATURE_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, SOAppliance):
        cavities = appliance_data.get_supported_cavities()

        entities.extend(
            ElectroluxSubmoduleSensor(appliance_data, coordinator, cavity, description)
            for description in STRUCTURED_OVEN_CAVITY_ELECTROLUX_SENSORS
            for cavity in cavities
            if description.exists_fn(appliance_data, cavity)
        )

    if isinstance(
        appliance_data, DWAppliance | TDAppliance | WDAppliance | WMAppliance
    ):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in CARE_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set sensor for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxBaseSensor[T: ApplianceData](
    ElectroluxBaseEntity[T], SensorEntity, ABC
):
    """Abstract base class for sensors of the Electrolux integration."""

    @override
    def _update_attr_state(self) -> bool:
        new_value = self._get_value()

        if self._attr_native_value != new_value:
            self._attr_native_value = new_value
            return True

        return False

    @abstractmethod
    def _get_value(self) -> StateType | datetime:
        raise NotImplementedError


class ElectroluxSensor[T: ApplianceData](ElectroluxBaseSensor[T]):
    """Representation of a generic sensor for Electrolux appliances."""

    entity_description: ElectroluxSensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSensorDescription[T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator, description.key)
        self.entity_description = description

        if isinstance(description, ElectroluxEnumSensorDescription):
            options = appliance_data.get_feature_state_string_options(
                description.feature_name
            )
            snake_case_options = [
                snake_case_option
                for option in options
                if (snake_case_option := convert_to_snake_case(option))
                in description.known_values
            ]

            if len(snake_case_options) > 0:
                self._attr_options = snake_case_options

    @override
    def _get_value(self) -> StateType | datetime:
        value = self.entity_description.value_fn(self._appliance_data)

        if isinstance(value, str) and isinstance(
            self.entity_description, ElectroluxEnumSensorDescription
        ):
            value = convert_to_snake_case(value)
            if self.entity_description.known_values:
                value = _map_to_known_value(
                    self.entity_description.known_values,
                    self.entity_description.key,
                    value,
                )

        return value


class ElectroluxTemperatureSensor[T: CRAppliance | OVAppliance](
    ElectroluxBaseSensor[T]
):
    """Representation of a temperature sensor for Electrolux appliances."""

    entity_description: ElectroluxTemperatureSensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxTemperatureSensorDescription[T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator, description.key)
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self.entity_description = description

    @override
    def _get_value(self) -> StateType:
        temp_unit = _get_temperature_unit(self._appliance_data)
        temp_value = self.entity_description.value_fn(self._appliance_data, temp_unit)
        if temp_value is None:
            return None
        return TemperatureConverter.convert(
            temp_value, temp_unit, UnitOfTemperature.CELSIUS
        )


class ElectroluxBaseSubmoduleSensor[T: ApplianceData](ElectroluxBaseSensor[T]):
    """Representation of a generic sensor for Electrolux appliances with submodules."""

    _submodule: str

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        submodule: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        entity_key = get_submodule_entity_key(submodule, description)
        translation_key = get_submodule_translation_key(submodule, description)

        super().__init__(appliance_data, coordinator, entity_key)
        self._submodule = submodule
        self._attr_translation_key = translation_key


class ElectroluxSubmoduleSensor[T: ApplianceData](ElectroluxBaseSubmoduleSensor[T]):
    """Representation of a generic sensor for Electrolux appliances with submodules."""

    entity_description: ElectroluxSubmoduleSensorDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        submodule: str,
        description: ElectroluxSubmoduleSensorDescription[T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator, submodule, description)
        self.entity_description = description

    @override
    def _get_value(self) -> StateType | datetime:
        description = self.entity_description

        return description.value_fn(self._appliance_data, self._submodule)


def _map_to_known_value(
    known_values: set[str], entity_key: str, value: str
) -> str | None:
    """Return provided value if it is known, otherwise log warn message and return None."""
    if value not in known_values:
        _LOGGER.warning(
            "An unknown value %s was reported for a sensor of the Electrolux integration. "
            "Please report it for the integration, and include the following information: "
            'entity key="%s", reported value="%s"',
            value,
            entity_key,
            value,
        )
        return None
    return value


def _get_temperature_unit(
    appliance: CRAppliance | OVAppliance | SOAppliance,
) -> UnitOfTemperature:
    temp_unit = appliance.get_current_temperature_unit()

    if temp_unit is not None:
        temp_unit = temp_unit.upper()

    return ELECTROLUX_TO_HA_TEMPERATURE_UNIT.get(temp_unit, UnitOfTemperature.CELSIUS)
