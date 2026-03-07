"""Enums for Nest."""

from enum import StrEnum, unique
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


@unique
class BucketType(StrEnum):
    """Bucket types."""

    BUCKETS = "buckets"
    DELAYED_TOPAZ = "delayed_topaz"
    DEMAND_RESPONSE = "demand_response"
    DEVICE = "device"
    DEVICE_ALERT_DIALOG = "device_alert_dialog"
    GEOFENCE_INFO = "geofence_info"
    KRYPTONITE = "kryptonite"  # Temperature Sensors
    LINK = "link"
    MESSAGE = "message"
    MESSAGE_CENTER = "message_center"
    METADATA = "metadata"
    OCCUPANCY = "occupancy"
    QUARTZ = "quartz"  # Cameras
    RCS_SETTINGS = "rcs_settings"
    SAFETY = "safety"
    SAFETY_SUMMARY = "safety_summary"
    SCHEDULE = "schedule"
    SHARED = "shared"
    STRUCTURE = "structure"  # General
    STRUCTURE_HISTORY = "structure_history"
    STRUCTURE_METADATA = "structure_metadata"
    TOPAZ = "topaz"  # Nest Protect
    TOPAZ_RESOURCE = "topaz_resource"
    TRACK = "track"
    TRIP = "trip"
    TUNEUPS = "tuneups"
    USER = "user"
    USER_ALERT_DIALOG = "user_alert_dialog"
    USER_SETTINGS = "user_settings"
    WIDGET_TRACK = "widget_track"
    WHERE = "where"  # Areas

    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls: type[BucketType], value: Any) -> BucketType:
        _LOGGER.warning("Unsupported value %s has been returned for %s", value, cls)
        return cls.UNKNOWN


@unique
class Environment(StrEnum):
    """Environment types."""

    FIELDTEST = "fieldtest"
    PRODUCTION = "production"


@unique
class TemperatureScale(StrEnum):
    """Temperature scales."""

    CELSIUS = "C"
    FAHRENHEIT = "F"


@unique
class ThermostatHvacState(StrEnum):
    """Nest Thermostat HVAC states."""

    OFF = "off"
    HEATING = "heating"
    COOLING = "cooling"
    FAN = "fan"


@unique
class ThermostatHvacMode(StrEnum):
    """Nest Thermostat HVAC modes."""

    OFF = "off"
    COOL = "cool"
    HEAT = "heat"
    RANGE = "range"  # heat-cool


@unique
class HotWaterMode(StrEnum):
    """Nest Heat Link hot water modes."""

    OFF = "off"
    SCHEDULE = "schedule"


@unique
class LockBoltState(StrEnum):
    """Nest x Yale Lock bolt states."""

    LOCKED = "locked"
    UNLOCKED = "unlocked"
    LOCKING = "locking"
    UNLOCKING = "unlocking"
    JAMMED = "jammed"
    UNKNOWN = "unknown"


@unique
class LockBoltActor(StrEnum):
    """Actor that last changed the Nest x Yale Lock state."""

    PHYSICAL = "physical"
    KEYPAD = "keypad"
    REMOTE = "remote"
    IMPLICIT = "implicit"
    VOICE = "voice"
    UNKNOWN = "unknown"


@unique
class StructureMode(StrEnum):
    """Nest Structure modes."""

    HOME = "home"
    AWAY = "away"
    SLEEP = "sleep"
    VACATION = "vacation"
