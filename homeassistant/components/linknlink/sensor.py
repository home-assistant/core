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
    """Return a function that reads a polled environmental value."""

    def _value(data: LinknLinkData) -> StateType:
        if data.environment_state is None:
            return None
        return data.environment_state.values.get(key)

    return _value


def _environment_available(data: LinknLinkData) -> bool:
    """Return whether polled environmental state is available."""
    return data.environment_state is not None


def _optional_environment_available(
    key: str,
) -> Callable[[LinknLinkData], bool]:
    """Return availability for an optional environmental peripheral."""

    def _available(data: LinknLinkData) -> bool:
        return (
            data.environment_state is not None
            and key in data.environment_state.available_fields
        )

    return _available


def _target_available(data: LinknLinkData) -> bool:
    """Return whether fresh radar target updates are available."""
    state = data.target_state
    return state is not None and state.subscribed and not state.stale


def _latest_target_value(
    value_fn: Callable[[UltraPositionUpdate], StateType],
) -> Callable[[LinknLinkData], StateType]:
    """Return a function that reads a value from the latest radar targets."""

    def _value(data: LinknLinkData) -> StateType:
        state = data.target_state
        if state is None or state.stale or state.latest_update is None:
            return None
        return value_fn(state.latest_update)

    return _value


SENSOR_DESCRIPTIONS: tuple[LinknLinkSensorEntityDescription, ...] = (
    LinknLinkSensorEntityDescription(
        key="nearest_horizontal_distance",
        translation_key="nearest_horizontal_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_latest_target_value(
            lambda update: update.nearest_horizontal_distance
        ),
        available_fn=_target_available,
    ),
    LinknLinkSensorEntityDescription(
        key="nearest_distance",
        translation_key="nearest_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_latest_target_value(lambda update: update.nearest_distance),
        available_fn=_target_available,
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
    # People the radar detects anywhere in its detection area, taken from
    # the same pushed radar update as the distance sensors.
    LinknLinkSensorEntityDescription(
        key="detected_people",
        translation_key="detected_people",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_latest_target_value(lambda update: update.target_count),
        available_fn=_target_available,
    ),
    # People inside any of the zones configured on the device.
    LinknLinkSensorEntityDescription(
        key="people_in_zones",
        translation_key="people_in_zones",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_environment_value("persons_in_fenced_zones"),
        available_fn=_environment_available,
    ),
    *(
        LinknLinkSensorEntityDescription(
            key=f"zone_{zone}_people",
            translation_key="zone_people",
            translation_placeholders={"zone_number": str(zone)},
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
