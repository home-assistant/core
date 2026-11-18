"""Constants for the Hikvision integration."""

from dataclasses import dataclass

DOMAIN = "hikvision"

# Default values
DEFAULT_PORT = 80


@dataclass(frozen=True, kw_only=True)
class ImageSelectSetting:
    """An image setting with a list of choices that the integration knows."""

    key: str
    # Matched case-insensitively: some firmware spells the same path differently.
    path: str
    enabled_by_default: bool = True
    # Options are shown by their lowercase key (the camera's value, lowercased
    # and with other characters turned into underscores) so that they can be
    # translated. Values such as shutter speeds are used as the camera reports
    # them instead.
    translate_options: bool = True


# The select platform makes a select of each of these and the sensor platform a
# read-only sensor when the camera offers only one choice. The translation key is the key.
IMAGE_SELECT_SETTINGS: tuple[ImageSelectSetting, ...] = (
    ImageSelectSetting(key="wdr", path="WDR/mode"),
    ImageSelectSetting(key="backlight_compensation_mode", path="BLC/BLCMode"),
    ImageSelectSetting(key="backlight_compensation", path="BLC/enabled"),
    ImageSelectSetting(key="highlight_compensation_mode", path="HLC/HLCMode"),
    ImageSelectSetting(key="day_night_mode", path="IrcutFilter/IrcutFilterType"),
    ImageSelectSetting(
        key="day_night_schedule_type",
        path="IrcutFilter/Schedule/scheduleType",
        enabled_by_default=False,
    ),
    ImageSelectSetting(
        key="night_to_day_sensitivity",
        path="IrcutFilter/nightToDayFilterLevel",
        enabled_by_default=False,
        translate_options=False,
    ),
    ImageSelectSetting(
        key="exposure_mode", path="Exposure/ExposureType", enabled_by_default=False
    ),
    ImageSelectSetting(
        key="p_iris_mode", path="Exposure/pIris/pIrisType", enabled_by_default=False
    ),
    ImageSelectSetting(
        key="smart_supplement_light_mode",
        path="Exposure/OverexposeSuppress/Type",
        enabled_by_default=False,
    ),
    ImageSelectSetting(
        key="shutter_speed", path="Shutter/ShutterLevel", translate_options=False
    ),
    ImageSelectSetting(
        key="max_shutter_speed",
        path="Shutter/maxShutterLevelLimit",
        enabled_by_default=False,
        translate_options=False,
    ),
    ImageSelectSetting(
        key="min_shutter_speed",
        path="Shutter/minShutterLevelLimit",
        enabled_by_default=False,
        translate_options=False,
    ),
    ImageSelectSetting(
        key="iris_level",
        path="Iris/IrisLevel",
        enabled_by_default=False,
        translate_options=False,
    ),
    ImageSelectSetting(
        key="color_mode", path="Color/grayScale/grayScaleMode", enabled_by_default=False
    ),
    ImageSelectSetting(key="noise_reduction", path="NoiseReduce/mode"),
    ImageSelectSetting(key="defog", path="Dehaze/DehazeMode", enabled_by_default=False),
    ImageSelectSetting(key="white_balance", path="WhiteBalance/WhiteBalanceStyle"),
    ImageSelectSetting(
        key="flip_direction", path="ImageFlip/ImageFlipStyle", enabled_by_default=False
    ),
    ImageSelectSetting(
        key="power_line_frequency",
        path="powerLineFrequency/powerLineFrequencyMode",
        enabled_by_default=False,
    ),
    ImageSelectSetting(
        key="supplement_light", path="SupplementLight/supplementLightMode"
    ),
    ImageSelectSetting(
        key="supplement_light_mode",
        path="SupplementLight/mode",
        enabled_by_default=False,
    ),
    ImageSelectSetting(
        key="light_brightness_mode",
        path="SupplementLight/mixedLightBrightnessRegulatMode",
    ),
    ImageSelectSetting(
        key="event_intelligence_brightness_mode",
        path="SupplementLight/EventIntelligenceModeCfg/brightnessRegulatMode",
        enabled_by_default=False,
    ),
    ImageSelectSetting(
        key="ir_light_mode", path="IrLight/mode", enabled_by_default=False
    ),
    ImageSelectSetting(key="scene_mode", path="Scene/mode", enabled_by_default=False),
    ImageSelectSetting(
        key="focus_mode", path="FocusConfiguration/focusStyle", enabled_by_default=False
    ),
    ImageSelectSetting(
        key="focus_distance_mode",
        path="FocusConfiguration/focusDistanceMode",
        enabled_by_default=False,
    ),
    ImageSelectSetting(
        key="focus_limit_mode",
        path="FocusConfiguration/focusLimited",
        enabled_by_default=False,
        translate_options=False,
    ),
    ImageSelectSetting(
        key="digital_slow_shutter_level", path="DSS/DSSLevel", enabled_by_default=False
    ),
    ImageSelectSetting(
        key="zoom_limit_ratio",
        path="ZoomLimit/ZoomLimitRatio",
        enabled_by_default=False,
        translate_options=False,
    ),
    ImageSelectSetting(
        key="capture_mode", path="CaptureMode/mode", enabled_by_default=False
    ),
)
