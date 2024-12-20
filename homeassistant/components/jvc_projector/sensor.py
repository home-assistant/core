"""Sensor platform for JVC Projector integration."""

from __future__ import annotations

from dataclasses import dataclass

from jvcprojector import const

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JVCSensorEntityDescription(SensorEntityDescription):
    """Describe JVC sensor entity."""

    enabled_default: bool = True


JVC_SENSORS = (
    JVCSensorEntityDescription(
        key=const.KEY_POWER,
        translation_key="jvc_power_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_POWER,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_PICTURE_MODE,
        translation_key="jvc_picture_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_LASER_VALUE,
        translation_key="jvc_laser_value",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_LASER_TIME,
        translation_key="jvc_laser_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_HDR_CONTENT_TYPE,
        translation_key="jvc_hdr_content_type",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_HDR_CONTENT_TYPE,
        enabled_default=False,
    ),
    # niche sensors that are disabled by default
    JVCSensorEntityDescription(
        key=const.KEY_HDR,
        translation_key="jvc_hdr_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_HDR_MODES,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_HDMI_INPUT_LEVEL,
        translation_key="jvc_hdmi_input_level",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_HDMI_INPUT_LEVEL,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_HDMI_COLOR_SPACE,
        translation_key="jvc_hdmi_color_space",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_HDMI_COLOR_SPACE,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_COLOR_PROFILE,
        translation_key="jvc_color_profile",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_GRAPHICS_MODE,
        translation_key="jvc_graphics_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_GRAPHICS_MODE,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_COLOR_SPACE,
        translation_key="jvc_color_space",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_MOTION_ENHANCE,
        translation_key="jvc_motion_enhance",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_MOTION_ENHANCE,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_CLEAR_MOTION_DRIVE,
        translation_key="jvc_clear_motion_drive",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_CLEAR_MOTION_DRIVE,
        enabled_default=False,
    ),
    JVCSensorEntityDescription(
        key=const.KEY_HDR_PROCESSING,
        translation_key="jvc_hdr_processing_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["0", "1", "2", "3"],  # translated
        enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: JVCConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        JvcSensor(coordinator, description) for description in JVC_SENSORS
    )


class JvcSensor(JvcProjectorEntity, SensorEntity):
    """The entity class for JVC Projector integration."""

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: JVCSensorEntityDescription,
    ) -> None:
        """Initialize the JVC Projector sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_entity_registry_enabled_default = description.enabled_default

    @property
    def native_value(self) -> str | None:
        """Return the native value."""
        return self.coordinator.data.get(self.entity_description.key)
