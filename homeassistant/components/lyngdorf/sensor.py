"""Sensor platform for Lyngdorf integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lyngdorf.device import Receiver

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
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
        value_fn=lambda r: r.audio_input,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="video_input",
        translation_key="video_input",
        value_fn=lambda r: r.video_input,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="streaming_source",
        translation_key="streaming_source",
        value_fn=lambda r: r.streaming_source,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ZONE_B_SENSORS: tuple[LyngdorfSensorEntityDescription, ...] = (
    LyngdorfSensorEntityDescription(
        key="zone_b_audio_input",
        translation_key="zone_b_audio_input",
        value_fn=lambda r: r.zone_b_audio_input,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="zone_b_streaming_source",
        translation_key="zone_b_streaming_source",
        value_fn=lambda r: r.zone_b_streaming_source,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lyngdorf sensors from a config entry."""
    receiver = config_entry.runtime_data.receiver
    device_info = config_entry.runtime_data.device_info

    entities: list[LyngdorfSensor] = [
        LyngdorfSensor(receiver, config_entry, device_info, description)
        for description in (*MAIN_ZONE_SENSORS, *ZONE_B_SENSORS)
    ]
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
        super().__init__(receiver)
        assert config_entry.unique_id
        self.entity_description = description
        self._attr_device_info = device_info
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

    @property
    def native_value(self) -> str | None:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self._receiver)
