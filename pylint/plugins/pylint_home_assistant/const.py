"""Constants for the pylint_home_assistant plugin package."""

from enum import StrEnum


class Platform(StrEnum):
    """Entity platform names.

    Inlined from ``homeassistant.const.Platform`` so the plugin package does
    not depend on the ``homeassistant`` package itself.
    """

    AIR_QUALITY = "air_quality"
    ALARM_CONTROL_PANEL = "alarm_control_panel"
    ASSIST_SATELLITE = "assist_satellite"
    BINARY_SENSOR = "binary_sensor"
    BUTTON = "button"
    CALENDAR = "calendar"
    CAMERA = "camera"
    CLIMATE = "climate"
    CONVERSATION = "conversation"
    COVER = "cover"
    DATE = "date"
    DATETIME = "datetime"
    DEVICE_TRACKER = "device_tracker"
    EVENT = "event"
    FAN = "fan"
    GEO_LOCATION = "geo_location"
    HUMIDIFIER = "humidifier"
    IMAGE = "image"
    IMAGE_PROCESSING = "image_processing"
    LAWN_MOWER = "lawn_mower"
    LIGHT = "light"
    LOCK = "lock"
    MEDIA_PLAYER = "media_player"
    NOTIFY = "notify"
    NUMBER = "number"
    REMOTE = "remote"
    SCENE = "scene"
    SELECT = "select"
    SENSOR = "sensor"
    SIREN = "siren"
    STT = "stt"
    SWITCH = "switch"
    TEXT = "text"
    TIME = "time"
    TODO = "todo"
    TTS = "tts"
    UPDATE = "update"
    VACUUM = "vacuum"
    WAKE_WORD = "wake_word"
    WATER_HEATER = "water_heater"
    WEATHER = "weather"


ENTITY_COMPONENTS: frozenset[str] = frozenset(p.value for p in Platform)


ANY_PLATFORM = "__any_platform__"
"""Synthetic key used in type hint match dicts for functions on any platform."""


class IntegrationType(StrEnum):
    """Integration types from manifest.json."""

    DEVICE = "device"
    ENTITY = "entity"
    HARDWARE = "hardware"
    HELPER = "helper"
    HUB = "hub"
    SERVICE = "service"
    SYSTEM = "system"
    VIRTUAL = "virtual"


class Module(StrEnum):
    """Well-known integration sub-module names."""

    INIT = "__init__"
    APPLICATION_CREDENTIALS = "application_credentials"
    BACKUP = "backup"
    CAST = "cast"
    CONFIG_FLOW = "config_flow"
    CONST = "const"
    COORDINATOR = "coordinator"
    DEVICE_ACTION = "device_action"
    DEVICE_CONDITION = "device_condition"
    DEVICE_TRIGGER = "device_trigger"
    DIAGNOSTICS = "diagnostics"
    ENTITY = "entity"
