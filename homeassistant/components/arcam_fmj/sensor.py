"""Arcam sensors for incoming stream info."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arcam.fmj import IncomingVideoAspectRatio, IncomingVideoColorspace
from arcam.fmj.state import IncomingAudioConfig, IncomingAudioFormat, State

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfFrequency
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ArcamFmjConfigEntry
from .entity import ArcamFmjEntity


@dataclass(frozen=True, kw_only=True)
class ArcamFmjSensorEntityDescription(SensorEntityDescription):
    """Describes an Arcam FMJ sensor entity."""

    value_fn: Callable[[State], int | float | str | None]


SENSORS: tuple[ArcamFmjSensorEntityDescription, ...] = (
    ArcamFmjSensorEntityDescription(
        key="incoming_video_horizontal_resolution",
        translation_key="incoming_video_horizontal_resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="px",
        suggested_display_precision=0,
        value_fn=lambda state: (
            vp.horizontal_resolution
            if (vp := state.get_incoming_video_parameters()) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_vertical_resolution",
        translation_key="incoming_video_vertical_resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="px",
        suggested_display_precision=0,
        value_fn=lambda state: (
            vp.vertical_resolution
            if (vp := state.get_incoming_video_parameters()) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_refresh_rate",
        translation_key="incoming_video_refresh_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        value_fn=lambda state: (
            vp.refresh_rate
            if (vp := state.get_incoming_video_parameters()) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_aspect_ratio",
        translation_key="incoming_video_aspect_ratio",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[member.name.lower() for member in IncomingVideoAspectRatio],
        value_fn=lambda state: (
            vp.aspect_ratio.name.lower()
            if (vp := state.get_incoming_video_parameters()) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_colorspace",
        translation_key="incoming_video_colorspace",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[member.name.lower() for member in IncomingVideoColorspace],
        value_fn=lambda state: (
            vp.colorspace.name.lower()
            if (vp := state.get_incoming_video_parameters()) is not None
            and vp.colorspace is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_format",
        translation_key="incoming_audio_format",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[member.name.lower() for member in IncomingAudioFormat],
        value_fn=lambda state: (
            result.name.lower()
            if (result := state.get_incoming_audio_format()[0]) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_config",
        translation_key="incoming_audio_config",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[member.name.lower() for member in IncomingAudioConfig],
        value_fn=lambda state: (
            result.name.lower()
            if (result := state.get_incoming_audio_format()[1]) is not None
            else None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_sample_rate",
        translation_key="incoming_audio_sample_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=0,
        value_fn=lambda state: (
            None
            if (sample_rate := state.get_incoming_audio_sample_rate()) == 0
            else sample_rate
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ sensors from a config entry."""
    coordinators = config_entry.runtime_data.coordinators

    entities: list[ArcamFmjSensorEntity] = []
    for coordinator in coordinators.values():
        entities.extend(
            ArcamFmjSensorEntity(coordinator, description) for description in SENSORS
        )
    async_add_entities(entities)


class ArcamFmjSensorEntity(ArcamFmjEntity, SensorEntity):
    """Representation of an Arcam FMJ sensor."""

    entity_description: ArcamFmjSensorEntityDescription

    @property
    def native_value(self) -> int | float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.state)
