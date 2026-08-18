"""Sensor platform for Lyngdorf integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from lyngdorf.device import Receiver

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LyngdorfSensorEntityDescription(SensorEntityDescription):
    """Describe a Lyngdorf sensor entity."""

    value_fn: Callable[[Receiver], str | None]
    options_fn: Callable[[Receiver], list[str]] | None = None


def _known(value: str | None, options: list[str]) -> str | None:
    """Return the value only if it is one of the device's known names."""
    return value if value in options else None


MAIN_ZONE_SENSORS: tuple[LyngdorfSensorEntityDescription, ...] = (
    LyngdorfSensorEntityDescription(
        key="audio_information",
        translation_key="audio_information",
        value_fn=lambda r: r.audio_information,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="video_information",
        translation_key="video_information",
        value_fn=lambda r: r.video_information,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="audio_input",
        translation_key="audio_input",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: _known(r.audio_input, r.available_audio_inputs),
        options_fn=lambda r: r.available_audio_inputs,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="video_input",
        translation_key="video_input",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: _known(r.video_input, r.available_video_inputs),
        options_fn=lambda r: r.available_video_inputs,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="streaming_source",
        translation_key="streaming_source",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: _known(r.streaming_source, r.available_stream_types),
        options_fn=lambda r: r.available_stream_types,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ZONE_B_SENSORS: tuple[LyngdorfSensorEntityDescription, ...] = (
    LyngdorfSensorEntityDescription(
        key="zone_b_audio_input",
        translation_key="zone_b_audio_input",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: _known(r.zone_b_audio_input, r.available_audio_inputs),
        options_fn=lambda r: r.available_audio_inputs,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="zone_b_streaming_source",
        translation_key="zone_b_streaming_source",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: _known(r.zone_b_streaming_source, r.available_stream_types),
        options_fn=lambda r: r.available_stream_types,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lyngdorf sensors from a config entry."""
    runtime_data = config_entry.runtime_data

    entities: list[LyngdorfSensor] = [
        LyngdorfSensor(
            runtime_data.receiver, config_entry, runtime_data.device_info, description
        )
        for description in MAIN_ZONE_SENSORS
    ]
    # Zone B sensors stay on the main device so they read "Zone B audio input"
    # rather than repeating the zone in the Zone B device's own name.
    if runtime_data.zone_b_device_info is not None:
        entities.extend(
            LyngdorfSensor(
                runtime_data.receiver,
                config_entry,
                runtime_data.device_info,
                description,
            )
            for description in ZONE_B_SENSORS
        )

    async_add_entities(entities)


class LyngdorfSensor(LyngdorfEntity, SensorEntity):
    """Lyngdorf sensor entity."""

    entity_description: LyngdorfSensorEntityDescription

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        description: LyngdorfSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(receiver, device_info)
        if TYPE_CHECKING:
            assert config_entry.unique_id
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

    @override
    @property
    def options(self) -> list[str] | None:
        """Return the device-reported options for enum sensors."""
        if (options_fn := self.entity_description.options_fn) is None:
            return None
        return options_fn(self._receiver)

    @override
    @property
    def native_value(self) -> str | None:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self._receiver)
