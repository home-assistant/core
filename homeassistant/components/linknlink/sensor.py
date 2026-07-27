"""Sensors for LinknLink eMotion Ultra."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiolinknlink import UltraPositionUpdate

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LinknLinkConfigEntry, LinknLinkData
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LinknLinkSensorEntityDescription(SensorEntityDescription):
    """Describe a LinknLink sensor."""

    value_fn: Callable[[LinknLinkData], StateType]
    available_fn: Callable[[LinknLinkData], bool]


def _environment_value(key: str) -> Callable[[LinknLinkData], StateType]:
    """Return a function that reads an environmental value."""

    def _value(data: LinknLinkData) -> StateType:
        if data.environment_state is None:
            return None
        return data.environment_state.values.get(key)

    return _value


def _environment_available(data: LinknLinkData) -> bool:
    """Return whether environmental state is available."""
    return data.environment_available and data.environment_state is not None


def _optional_environment_available(
    key: str,
) -> Callable[[LinknLinkData], bool]:
    """Return availability for an optional environmental peripheral."""

    def _available(data: LinknLinkData) -> bool:
        return (
            _environment_available(data)
            and data.environment_state is not None
            and key in data.environment_state.available_fields
        )

    return _available


def _position_available(data: LinknLinkData) -> bool:
    """Return whether local target positions are available."""
    return data.position_state is not None and data.position_state.subscribed


def _latest_position_value(
    value_fn: Callable[[UltraPositionUpdate], StateType],
) -> Callable[[LinknLinkData], StateType]:
    """Return a function that reads a value from the latest target positions."""

    def _value(data: LinknLinkData) -> StateType:
        state = data.position_state
        if state is None or state.stale or state.latest_update is None:
            return None
        return value_fn(state.latest_update)

    return _value


def _target_count(data: LinknLinkData) -> StateType:
    """Return the freshest available detected-target count."""
    state = data.position_state
    if (
        state is not None
        and state.subscribed
        and not state.stale
        and state.latest_update is not None
    ):
        return state.latest_update.target_count
    return _environment_value("target_count")(data)


def _target_count_available(data: LinknLinkData) -> bool:
    """Return whether either source for detected-target count is available."""
    state = data.position_state
    return (
        state is not None
        and state.subscribed
        and not state.stale
        and state.latest_update is not None
    ) or _environment_available(data)


SENSOR_DESCRIPTIONS: tuple[LinknLinkSensorEntityDescription, ...] = (
    LinknLinkSensorEntityDescription(
        key="nearest_horizontal_distance",
        translation_key="nearest_horizontal_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_latest_position_value(
            lambda update: update.nearest_horizontal_distance
        ),
        available_fn=_position_available,
    ),
    LinknLinkSensorEntityDescription(
        key="nearest_distance",
        translation_key="nearest_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_latest_position_value(lambda update: update.nearest_distance),
        available_fn=_position_available,
    ),
    LinknLinkSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_environment_value("temperature"),
        available_fn=_optional_environment_available("temperature"),
    ),
    LinknLinkSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_environment_value("humidity"),
        available_fn=_optional_environment_available("humidity"),
    ),
    LinknLinkSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_environment_value("illuminance"),
        available_fn=_environment_available,
    ),
    LinknLinkSensorEntityDescription(
        key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_environment_value("wifi_signal"),
        available_fn=_environment_available,
    ),
    LinknLinkSensorEntityDescription(
        key="target_count",
        translation_key="target_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_target_count,
        available_fn=_target_count_available,
    ),
    LinknLinkSensorEntityDescription(
        key="persons_in_fenced_zones",
        translation_key="persons_in_fenced_zones",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_environment_value("persons_in_fenced_zones"),
        available_fn=_environment_available,
    ),
    *(
        LinknLinkSensorEntityDescription(
            key=f"zone_{zone}_target_counts",
            translation_key=f"zone_{zone}_target_count",
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=_environment_value(f"zone_{zone}_target_counts"),
            available_fn=_environment_available,
        )
        for zone in range(1, 5)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LinknLink sensors."""
    async_add_entities(
        LinknLinkSensor(entry.runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
    )


class LinknLinkSensor(LinknLinkEntity, SensorEntity):
    """Representation of a LinknLink sensor."""

    entity_description: LinknLinkSensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether the sensor's local data source is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the latest locally reported value."""
        return self.entity_description.value_fn(self.coordinator.data)
