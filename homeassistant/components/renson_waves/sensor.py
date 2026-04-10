"""Sensor platform for Renson WAVES."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RensonWavesConfigEntry
from .coordinator import RensonWavesData
from .entity import RensonWavesEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RensonWavesSensorDescription(SensorEntityDescription):
    """Description of a Renson WAVES sensor."""

    value_fn: Callable[[RensonWavesData], StateType]


def _constellation_value_fn(
    sensor_id: str,
    parameter_key: str,
) -> Callable[[RensonWavesData], StateType]:
    """Build a typed extractor for constellation sensor values."""

    def _value_fn(data: RensonWavesData) -> StateType:
        return cast(
            StateType,
            data.constellation.get("sensor", {})
            .get(sensor_id, {})
            .get("parameter", {})
            .get(parameter_key, {})
            .get("value"),
        )

    return _value_fn


FIXED_SENSORS: tuple[RensonWavesSensorDescription, ...] = (
    RensonWavesSensorDescription(
        key="uptime_seconds",
        translation_key="uptime_seconds",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: (
            data.uptime.get("global", {}).get("uptime", {}).get("value")
        ),
    ),
    RensonWavesSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        value_fn=lambda data: (
            data.wifi_status.get("global", {}).get("ssid", {}).get("value")
        ),
    ),
    RensonWavesSensorDescription(
        key="room_boost_mode",
        translation_key="room_boost_mode",
        value_fn=lambda data: (
            data.decision_room.get("global", {}).get("decision", {}).get("value")
        ),
    ),
    RensonWavesSensorDescription(
        key="room_boost_level",
        translation_key="room_boost_level",
        value_fn=lambda data: (
            data.decision_room.get("global", {}).get("level", {}).get("value")
        ),
    ),
    RensonWavesSensorDescription(
        key="silent_reduction",
        translation_key="silent_reduction",
        value_fn=lambda data: (
            data.decision_silent.get("global", {}).get("reduction", {}).get("value")
        ),
    ),
    RensonWavesSensorDescription(
        key="silent_mode",
        translation_key="silent_mode",
        value_fn=lambda data: (
            data.decision_silent.get("global", {}).get("decision", {}).get("value")
        ),
    ),
    RensonWavesSensorDescription(
        key="breeze_temperature",
        translation_key="breeze_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            data.decision_breeze.get("global", {}).get("temperature", {}).get("value")
        ),
    ),
    RensonWavesSensorDescription(
        key="breeze_mode",
        translation_key="breeze_mode",
        value_fn=lambda data: (
            data.decision_breeze.get("global", {}).get("decision", {}).get("value")
        ),
    ),
)


class RensonWavesSensor(RensonWavesEntity, SensorEntity):
    """Sensor for Renson WAVES."""

    entity_description: RensonWavesSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the native value."""
        return self.entity_description.value_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RensonWavesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    serial = coordinator.client.host

    constellation = coordinator.data.constellation
    if constellation:
        global_data = constellation.get("global", {})
        serial = (
            global_data.get("serial", {}).get("value")
            or f"{coordinator.client.host}:{coordinator.client.port}"
        )

    entities: list[SensorEntity] = [
        RensonWavesSensor(
            coordinator=coordinator,
            description=description,
            serial=serial,
        )
        for description in FIXED_SENSORS
    ]

    if constellation:
        sensor_data = constellation.get("sensor", {})
        for sensor_id, sensor_info in sensor_data.items():
            sensor_type = sensor_info.get("type")
            parameters = sensor_info.get("parameter", {})

            for param_key, param_data in parameters.items():
                unit = param_data.get("unit", "")
                description = RensonWavesSensorDescription(
                    key=f"constellation_{sensor_id}_{param_key}",
                    translation_key=f"constellation_{sensor_type}_{param_key}",
                    native_unit_of_measurement=unit or None,
                    value_fn=_constellation_value_fn(sensor_id, param_key),
                )
                entities.append(
                    RensonWavesSensor(
                        coordinator=coordinator,
                        description=description,
                        serial=serial,
                    )
                )

    async_add_entities(entities)
