"""Sensor platform for JVC Projector integration."""

from __future__ import annotations

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

JVC_SENSORS = (
    SensorEntityDescription(
        key=const.KEY_POWER,
        translation_key="jvc_power_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            const.STANDBY,
            const.ON,
            const.WARMING,
            const.COOLING,
            const.ERROR,
        ],
    ),
    SensorEntityDescription(
        key=const.KEY_INPUT,
        translation_key="jvc_hdmi_input",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            const.HDMI1,
            const.HDMI2,
        ],
    ),
    SensorEntityDescription(
        key=const.KEY_SOURCE,
        translation_key="jvc_source_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            const.SIGNAL,
            const.NOSIGNAL,
        ],
    ),
    SensorEntityDescription(
        key=const.KEY_PICTURE_MODE,
        translation_key="jvc_picture_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=const.KEY_LOW_LATENCY,
        translation_key="jvc_low_latency_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            const.OFF,
            const.ON,
        ],
    ),
    SensorEntityDescription(
        key=const.KEY_INSTALLATION_MODE,
        translation_key="jvc_installation_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=const.KEY_ANAMORPHIC,
        translation_key="jvc_anamorphic_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            const.OFF,
            const.ANAMORPHIC_A,
            const.ANAMORPHIC_B,
            const.ANAMORPHIC_C,
            const.ANAMORPHIC_D,
        ],
    ),
    SensorEntityDescription(
        key=const.KEY_HDR,
        translation_key="jvc_hdr_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            const.HDR_CONTENT_NONE,
            const.HDR_CONTENT_HDR10,
            const.HDR_CONTENT_HDR10PLUS,
            const.HDR_CONTENT_HLG,
            const.HDR_CONTENT_SDR,
        ],
    ),
    SensorEntityDescription(
        key=const.KEY_HDMI_INPUT_LEVEL,
        translation_key="jvc_hdmi_input_level",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_HDMI_INPUT_LEVEL,
    ),
    SensorEntityDescription(
        key=const.KEY_HDMI_COLOR_SPACE,
        translation_key="jvc_hdmi_color_space",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_HDMI_COLOR_SPACE,
    ),
    SensorEntityDescription(
        key=const.KEY_COLOR_PROFILE,
        translation_key="jvc_color_profile",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=const.KEY_GRAPHICS_MODE,
        translation_key="jvc_graphics_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_GRAPHICS_MODE,
    ),
    SensorEntityDescription(
        key=const.KEY_COLOR_SPACE,
        translation_key="jvc_color_space",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_COLOR_SPACE,
    ),
    SensorEntityDescription(
        key=const.KEY_ESHIFT,
        translation_key="jvc_eshift",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            const.OFF,
            const.ON,
        ],
    ),
    SensorEntityDescription(
        key=const.KEY_LASER_DIMMING,
        translation_key="jvc_laser_dimming_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_LASER_DIMMING,
    ),
    SensorEntityDescription(
        key=const.KEY_LASER_VALUE,
        translation_key="jvc_laser_value",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=const.KEY_LASER_POWER,
        translation_key="jvc_laser_power",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_LASER_POWER,
    ),
    SensorEntityDescription(
        key=const.KEY_LASER_TIME,
        translation_key="jvc_laser_time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=const.KEY_MOTION_ENHANCE,
        translation_key="jvc_motion_enhance",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_MOTION_ENHANCE,
    ),
    SensorEntityDescription(
        key=const.KEY_CLEAR_MOTION_DRIVE,
        translation_key="jvc_clear_motion_drive",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_CLEAR_MOTION_DRIVE,
    ),
    SensorEntityDescription(
        key=const.KEY_HDR_PROCESSING,
        translation_key="jvc_hdr_processing_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_HDR_PROCESSING,
    ),
    SensorEntityDescription(
        key=const.KEY_HDR_CONTENT_TYPE,
        translation_key="jvc_hdr_content_type",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=const.VAL_HDR_CONTENT_TYPE,
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
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the JVC Projector sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def native_value(self) -> str | None:
        """Return the native value."""
        return self.coordinator.data[self.entity_description.key]
