"""Sensor platform for Lyngdorf integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from lyngdorf import LyngdorfReceiver, Reading, VolumeControl

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LyngdorfSensorEntityDescription(SensorEntityDescription):
    """Describe a Lyngdorf sensor entity."""

    value_fn: Callable[[LyngdorfReceiver], float | None] | None = None
    reading_fn: Callable[[LyngdorfReceiver], Reading | None] | None = None


def _known(value: str | None, options: list[str]) -> str | None:
    """Return the value only if it is one of the device's known names."""
    return value if value in options else None


MAIN_ZONE_SENSORS: tuple[LyngdorfSensorEntityDescription, ...] = (
    LyngdorfSensorEntityDescription(
        key="audio_information",
        translation_key="audio_information",
        reading_fn=lambda r: r.audio_information_reading,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="video_information",
        translation_key="video_information",
        reading_fn=lambda r: r.video_information_reading,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="audio_input",
        translation_key="audio_input",
        device_class=SensorDeviceClass.ENUM,
        reading_fn=lambda r: r.audio_input_reading,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="video_input",
        translation_key="video_input",
        device_class=SensorDeviceClass.ENUM,
        reading_fn=lambda r: r.video_input_reading,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="streaming_source",
        translation_key="streaming_source",
        device_class=SensorDeviceClass.ENUM,
        reading_fn=lambda r: r.streaming_source_reading,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ZONE_B_SENSORS: tuple[LyngdorfSensorEntityDescription, ...] = (
    LyngdorfSensorEntityDescription(
        key="zone_b_audio_input",
        translation_key="zone_b_audio_input",
        device_class=SensorDeviceClass.ENUM,
        reading_fn=lambda r: zb.audio_input_reading if (zb := r.zone_b) else None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LyngdorfSensorEntityDescription(
        key="zone_b_streaming_source",
        translation_key="zone_b_streaming_source",
        device_class=SensorDeviceClass.ENUM,
        reading_fn=lambda r: zb.streaming_source_reading if (zb := r.zone_b) else None,
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
    receiver = runtime_data.receiver
    registry = er.async_get(hass)

    descriptions = list(MAIN_ZONE_SENSORS)
    # Zone B sensors stay on the main device so they read "Zone B audio input"
    # rather than repeating the zone in the Zone B device's own name.
    if runtime_data.zone_b_device_info is not None:
        descriptions.extend(ZONE_B_SENSORS)

    entities: list[LyngdorfSensor] = []
    for description in descriptions:
        if TYPE_CHECKING:
            assert description.reading_fn
        if description.reading_fn(receiver) is not None:
            entities.append(
                LyngdorfSensor(
                    receiver, config_entry, runtime_data.device_info, description
                )
            )
        elif entity_id := registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, f"{config_entry.unique_id}_{description.key}"
        ):
            registry.async_remove(entity_id)

    if isinstance(receiver.volume, VolumeControl):
        entities.append(
            LyngdorfSensor(
                receiver,
                config_entry,
                runtime_data.device_info,
                MAXIMUM_VOLUME_SENSOR,
            )
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
        if self.entity_description.device_class is not SensorDeviceClass.ENUM:
            return None
        reading = self._reading()
        return reading.options if reading is not None else None

    @override
    @property
    def native_value(self) -> str | float | None:
        """Return the current sensor value."""
        if (value_fn := self.entity_description.value_fn) is not None:
            return value_fn(self._receiver)
        if (reading := self._reading()) is None:
            return None
        if self.entity_description.device_class is SensorDeviceClass.ENUM:
            return _known(reading.value, reading.options)
        return reading.value

    def _reading(self) -> Reading | None:
        if (reading_fn := self.entity_description.reading_fn) is None:
            return None
        return reading_fn(self._receiver)
