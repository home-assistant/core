"""Sensor platform for Lyngdorf integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from lyngdorf import LyngdorfReceiver, VolumeControl

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LyngdorfSensorEntityDescription(SensorEntityDescription):
    """Describe a Lyngdorf sensor entity."""

    value_fn: Callable[[LyngdorfReceiver], str | float | None]
    options_fn: Callable[[LyngdorfReceiver], list[str]] | None = None


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
        value_fn=lambda r: _known(r.audio_input, r.audio_inputs),
        options_fn=lambda r: r.audio_inputs,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="video_input",
        translation_key="video_input",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: _known(r.video_input, r.video_inputs),
        options_fn=lambda r: r.video_inputs,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="streaming_source",
        translation_key="streaming_source",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: _known(r.streaming_source, r.stream_types),
        options_fn=lambda r: r.stream_types,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ZONE_B_SENSORS: tuple[LyngdorfSensorEntityDescription, ...] = (
    LyngdorfSensorEntityDescription(
        key="zone_b_audio_input",
        translation_key="zone_b_audio_input",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: (
            _known(zb.audio_input, r.audio_inputs) if (zb := r.zone_b) else None
        ),
        options_fn=lambda r: r.audio_inputs,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="zone_b_streaming_source",
        translation_key="zone_b_streaming_source",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda r: (
            _known(zb.streaming_source, r.stream_types) if (zb := r.zone_b) else None
        ),
        options_fn=lambda r: r.stream_types,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


# Only the models that report `!MAXVOL` carry a VolumeControl, so the ceiling
# sensor is created from the control's type. Its value stays None until the
# device first reports one, which never means the model has no ceiling.
MAXIMUM_VOLUME_SENSOR = LyngdorfSensorEntityDescription(
    key="maximum_volume",
    translation_key="maximum_volume",
    native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
    value_fn=lambda r: (
        volume.maximum_volume if isinstance(volume := r.volume, VolumeControl) else None
    ),
    entity_category=EntityCategory.DIAGNOSTIC,
    # Most owners set no ceiling, so this would read the same value forever.
    entity_registry_enabled_default=False,
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
    if isinstance(runtime_data.receiver.volume, VolumeControl):
        entities.append(
            LyngdorfSensor(
                runtime_data.receiver,
                config_entry,
                runtime_data.device_info,
                MAXIMUM_VOLUME_SENSOR,
            )
        )

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
        receiver: LyngdorfReceiver,
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
    def native_value(self) -> str | float | None:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self._receiver)
