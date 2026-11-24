"""Constants for the Hikvision integration."""

from dataclasses import dataclass

DOMAIN = "hikvision"

# Whether pyHik made up the entry's unique ID, a random one, because the device's
# own ID is too short. Not known for entries created before it was recorded.
CONF_RANDOM_ID = "random_id"

# Default values
DEFAULT_PORT = 80


@dataclass(frozen=True, kw_only=True)
class ImageSwitchSetting:
    """An on/off image setting that the integration knows."""

    key: str
    # Matched case-insensitively: some firmware spells the same path differently.
    path: str
    enabled_by_default: bool = False


# The switch platform makes a switch of each of these, and the sensor platform a
# read-only sensor when the camera offers only one of the two values. The
# translation key is the key.
IMAGE_SWITCH_SETTINGS: tuple[ImageSwitchSetting, ...] = (
    # Only a camera that has the flag without a mode to go with it gets this one: pyHik
    # folds the flag into the mode, which is then a select.
    ImageSwitchSetting(key="backlight_compensation", path="BLC/enabled"),
    ImageSwitchSetting(
        key="highlight_compensation", path="HLC/enabled", enabled_by_default=True
    ),
    ImageSwitchSetting(
        key="smart_supplement_light",
        path="Exposure/OverexposeSuppress/enabled",
        enabled_by_default=True,
    ),
    ImageSwitchSetting(key="image_flip", path="ImageFlip/enabled"),
    # Called corridor mode by ISAPI: the picture is turned a quarter turn.
    ImageSwitchSetting(key="rotate", path="corridor/enabled"),
    ImageSwitchSetting(
        key="lens_distortion_correction", path="LensDistortionCorrection/enabled"
    ),
    ImageSwitchSetting(key="image_stabilization", path="EIS/enabled"),
    ImageSwitchSetting(key="digital_slow_shutter", path="DSS/enabled"),
    ImageSwitchSetting(key="image_freeze", path="ImageFreeze/enabled"),
    ImageSwitchSetting(key="lens_initialization", path="LensInitialization/enabled"),
    ImageSwitchSetting(key="proportional_pan", path="proportionalpan/enabled"),
    ImageSwitchSetting(key="image_loss_detection", path="enableImageLossDetection"),
)


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
        # The camera UI's video standard: PAL at 50 Hz, NTSC at 60 Hz.
        key="video_standard",
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

# Fired when the camera changed a setting on its own, or only applies one once it
# restarts: the logbook describes it.
EVENT_IMAGE_SETTING_CHANGED = f"{DOMAIN}_image_setting_changed"
ATTR_NAME = "name"
ATTR_MESSAGE = "message"
