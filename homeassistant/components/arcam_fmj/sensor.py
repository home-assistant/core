"""Arcam sensors for incoming stream info."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arcam.fmj.state import State

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfFrequency
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator


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
        value_fn=lambda state: getattr(
            state.get_incoming_video_parameters(), "horizontal_resolution", None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_vertical_resolution",
        translation_key="incoming_video_vertical_resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="px",
        suggested_display_precision=0,
        value_fn=lambda state: getattr(
            state.get_incoming_video_parameters(), "vertical_resolution", None
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
        value_fn=lambda state: getattr(
            state.get_incoming_video_parameters(), "refresh_rate", None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_aspect_ratio",
        translation_key="incoming_video_aspect_ratio",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            getattr(state.get_incoming_video_parameters(), "aspect_ratio", None),
            "name",
            None,
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_video_colorspace",
        translation_key="incoming_video_colorspace",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            getattr(state.get_incoming_video_parameters(), "colorspace", None),
            "name",
            None,
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_format",
        translation_key="incoming_audio_format",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            state.get_incoming_audio_format()[0], "name", None
        ),
    ),
    ArcamFmjSensorEntityDescription(
        key="incoming_audio_config",
        translation_key="incoming_audio_config",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            state.get_incoming_audio_format()[1], "name", None
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
        value_fn=lambda state: state.get_incoming_audio_sample_rate(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ sensors from a config entry."""
    coordinators = config_entry.runtime_data.coordinators
    uuid = config_entry.unique_id or config_entry.entry_id
    device_info = DeviceInfo(
        identifiers={(DOMAIN, uuid)},
        manufacturer="Arcam",
        model="Arcam FMJ AVR",
        name=config_entry.title,
    )

    entities: list[ArcamFmjSensorEntity] = []
    for zone in (1, 2):
        coordinator = coordinators[zone]
        entities.extend(
            ArcamFmjSensorEntity(
                device_info=device_info,
                uuid=uuid,
                coordinator=coordinator,
                description=description,
            )
            for description in SENSORS
        )
    async_add_entities(entities)


class ArcamFmjSensorEntity(CoordinatorEntity[ArcamFmjCoordinator], SensorEntity):
    """Representation of an Arcam FMJ sensor."""

    entity_description: ArcamFmjSensorEntityDescription
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        device_info: DeviceInfo,
        uuid: str,
        coordinator: ArcamFmjCoordinator,
        description: ArcamFmjSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._state = coordinator.state
        self._attr_unique_id = f"{uuid}-{self._state.zn}-{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"zone": str(self._state.zn)}

    @property
    def native_value(self) -> int | float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._state)
