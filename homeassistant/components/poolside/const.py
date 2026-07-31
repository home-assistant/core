"""Constants for the Poolside integration."""

from enum import StrEnum
import logging

DOMAIN = "poolside"

LOGGER = logging.getLogger(__package__)

DEFAULT_PORT = 8126
DEFAULT_CLIENT_NAME = "Home Assistant"

ZEROCONF_TYPE = "_poolside._tcp.local."
ZEROCONF_PROP_UUID = "uuid"
ZEROCONF_PROP_NAME = "name"

NOISE_PROLOGUE = b"PoolsideHomeAssistant/1"
NOISE_PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_SHA256"

CONF_CLIENT_PRIVATE_KEY = "client_private_key"
CONF_CONTROLLER_PUBLIC_KEY = "controller_public_key"
CONF_CONTROLLER_UUID = "controller_uuid"
CONF_CLIENT_NAME = "client_name"

# Options
CONF_EXPOSE_POOL_DEVICES = "expose_pool_devices"
DEFAULT_EXPOSE_POOL_DEVICES = True

PING_INTERVAL = 30
PING_TIMEOUT = 10
PAIRING_TIMEOUT = 300

# Periodic safety-net re-fetch of the full status snapshot, in case an
# incremental setStatus push was ever missed.
STATUS_REFRESH_INTERVAL = 300

RECONNECT_INITIAL_DELAY = 1
RECONNECT_MAX_DELAY = 60


class StatusState(StrEnum):
    """The STATUS_STATE enum reported by the controller for every control."""

    OFF = "OFF"
    ON = "ON"
    DISABLED = "DISABLED"


class ControlType(StrEnum):
    """The USER_CONTROL_TYPE enum reported by the controller for every control."""

    TEMPERATURE = "TEMPERATURE"
    LIGHT = "LIGHT"
    WATER_FEATURE = "WATER_FEATURE"
    CLEANER = "CLEANER"
    FILTER = "FILTER"
    BLOWER = "BLOWER"
    UNKNOWN = "UNKNOWN"


# Fallback mapping for controller responses that report a lowercase "type"
# slug instead of the ControlType enum name directly (Site.getControlLayout
# reports the enum name, e.g. "TEMPERATURE"; older/raw shapes may not).
CONTROL_TYPE_MAP: dict[str, ControlType] = {
    "heating": ControlType.TEMPERATURE,
    "temperature": ControlType.TEMPERATURE,
    "light": ControlType.LIGHT,
    "waterfeature": ControlType.WATER_FEATURE,
    "cleaner": ControlType.CLEANER,
    "filter": ControlType.FILTER,
    "blower": ControlType.BLOWER,
}

# Control types that may be plain on/off (a single SpeedIncrements entry) or
# variable-speed (more than one), decided per-control rather than per-type.
# BLOWER never varies (no SpeedIncrements in its layout at all) but is safe
# to include: speed_increments() defaults to [100] -> is_variable_speed False.
VARIABLE_SPEED_CONTROL_TYPES = (
    ControlType.WATER_FEATURE,
    ControlType.CLEANER,
    ControlType.FILTER,
    ControlType.BLOWER,
)

# Icon-only translation keys per control type, applied by both the fan and
# switch platforms (a control can render on either); the icons live in
# icons.json under both domains. Names still come from the control.
ICON_TRANSLATION_KEYS = {
    ControlType.WATER_FEATURE: "water_feature",
    ControlType.FILTER: "filter",
}


class GroupKind(StrEnum):
    """The Kind of a Site.getControlLayout group."""

    BODY_OF_WATER = "BODY_OF_WATER"
    LANDSCAPE = "LANDSCAPE"


class BodyOfWaterState(StrEnum):
    """The FRIENDLY_STATE a body of water reports via its CurrentState field."""

    OFF = "OFF"
    FILTERING = "FILTERING"
    HEATING = "HEATING"
    COOLING = "COOLING"
    ON = "ON"
    CRITICAL_ALERT = "CRITICAL_ALERT"
    COOLDOWN = "COOLDOWN"
    INSTALLER_MODE = "INSTALLER_MODE"


class SiteMode(StrEnum):
    """The controller-wide MODE reported under the site UUID.

    The controller only accepts desired-state writes in NORMAL mode, and
    INSTALLER mode additionally takes every control out of service from the
    user's point of view.
    """

    NORMAL = "NORMAL"
    INSTALLER = "INSTALLER"
    FAULT = "FAULT"
    FACTORY = "FACTORY"


class ControlMode(StrEnum):
    """Valid values for a TEMPERATURE control's ControlMode field."""

    AUTO = "AUTO"
    HEAT = "HEAT"
    COOL = "COOL"


class HeatingMode(StrEnum):
    """Valid values for a TEMPERATURE control's HeatingMode field."""

    SMART = "SMART"
    SOLAR = "SOLAR"
    HEATPUMP = "HEATPUMP"
    FUEL = "FUEL"


class CoolingMode(StrEnum):
    """Valid values for a TEMPERATURE control's CoolingMode field."""

    SMART = "SMART"
    HEATPUMP = "HEATPUMP"
    CHILLER = "CHILLER"


# Layout fields (Site.getControlLayout)
STATUS_FIELD = "Status"
PRIORITY_FIELD = "Priority"
WINTERIZED_FIELD = "Winterized"
MIN_SET_POINT_FIELD = "MinSetPoint"
MAX_SET_POINT_FIELD = "MaxSetPoint"
SUPPORTS_COLORS_FIELD = "SupportsColors"
DEFAULT_COLOR_FIELD = "DefaultColor"
SPEED_INCREMENTS_FIELD = "SpeedIncrements"
COMBINED_CONTROL_UUID_FIELD = "CombinedControlUUID"
MEMBER_CONTROL_UUIDS_FIELD = "MemberControlUUIDs"

# TEMPERATURE control capability lists. Reported with the control layout
# and pushed via Device.setStatus when they change; pushes have been
# observed keyed both by the group's BodyOfWaterUUID and by the heater
# control's own UUID, so lookups check every key before falling back to
# the layout.
CONTROL_MODES_SUPPORTED_FIELD = "ControlModesSupported"
HEATING_MODES_SUPPORTED_FIELD = "HeatingModesSupported"
COOLING_MODES_SUPPORTED_FIELD = "CoolingModesSupported"

# Body-of-water status items (Device.setStatus, keyed by BodyOfWaterUUID)
CURRENT_TEMPERATURE_FIELD = "Temperature"
CURRENT_STATE_FIELD = "CurrentState"

# Site-level status items (Device.setStatus, keyed by the site UUID from
# Site.getControlLayout). LastTimeSiteWasLoaded changes whenever the
# attendant's site configuration is edited - a signal to re-fetch the
# control layout and reload the entry. Mode is the controller-wide SiteMode.
LAST_TIME_SITE_WAS_LOADED_FIELD = "LastTimeSiteWasLoaded"
SITE_MODE_FIELD = "Mode"

# unique_id suffix of the site mode sensor - the one entity not keyed to a
# control or body-of-water UUID from the layout.
SITE_MODE_KEY = "site_mode"

# On/off IS pushed via Device.setStatus after all (observed live, keyed by
# the control's own UUID) - just under different field names than the
# Status write field: PowerState (what was requested) and ActualPowerState
# (ground truth - what the hardware is really doing). ActualPowerState
# should win whenever both are known.
POWER_STATE_FIELD = "PowerState"
ACTUAL_POWER_STATE_FIELD = "ActualPowerState"

# ActualPowerState (and possibly other power-state fields) can carry this
# literal sentinel when the controller can't confirm ground truth for a
# control (e.g. hardware without relay-state feedback) - treat it as "no
# data", not as a real value, so lookups fall through to the next field.
UNKNOWN_POWER_STATE = "UNKNOWN"

# Pushed keyed by the control's own UUID: the hard reasons a control is out
# of service, as a list of strings - "WINTERIZED", "FREEZE_PROTECT", or the
# UUID of the pool cover holding it closed. A control whose Status is merely
# DISABLED *without* any reason listed here is still operable: that Status is
# a suggestion that activating it will turn something else off.
DISABLED_REASONS_FIELD = "DisabledReasons"

# Known DisabledReasons values; any other entry is the UUID of the pool
# cover holding the control closed.
WINTERIZED_REASON = "WINTERIZED"
FREEZE_PROTECT_REASON = "FREEZE_PROTECT"

# Per-control desired-state fields. Not (yet, as far as observed) pushed by
# Device.setStatus; tracked optimistically from our own successful
# Device.setDesiredState2 writes instead.
SET_POINT_FIELD = "SetPoint"
CONTROL_MODE_FIELD = "ControlMode"
HEATING_MODE_FIELD = "HeatingMode"
COOLING_MODE_FIELD = "CoolingMode"
POWER_LEVEL_FIELD = "PowerLevel"
BRIGHTNESS_FIELD = "Brightness"
LIGHT_NAME_FIELD = "LightName"
SPEED_FIELD = "Speed"
TWINKLE_FIELD = "Twinkle"

# Pool devices are the physical hardware (pumps, heaters, ...) the controller
# operates to satisfy control requests; users never command them directly, so
# they surface only as read-only telemetry. Site.getPoolDevices lists them
# (UUID, Name, and DeviceType); everything else arrives as status pushes
# keyed by the device's UUID. InformationFields is itself such a push: a JSON
# list describing which of the device's status fields carry displayable
# telemetry and how to interpret each one.
INFORMATION_FIELDS_FIELD = "InformationFields"

# Keys of an InformationFields entry.
FIELD_NAME_KEY = "Name"
FIELD_DISPLAY_NAME_KEY = "DisplayName"
FIELD_DISPLAY_ORDER_KEY = "DisplayOrder"
FIELD_PROCESSING_LOGIC_KEY = "DisplayProcessingLogic"
FIELD_TYPES_KEY = "FieldTypes"

# The FieldTypes entry marking a field as read-only telemetry.
INFORMATION_FIELD_TYPE = "INFORMATION"

# Light pool devices push their Twinkle vocabulary here: a JSON array of
# {value, description} used to translate the raw Twinkle value. A supporting
# state only - never shown as a sensor of its own.
TWINKLE_INCREMENTS_FIELD = "TwinkleIncrements"

# DeviceType (casing varies by firmware) of light pool devices, which never
# publish an InformationFields document.
LIGHT_DEVICE_TYPE = "light"

# DeviceType prefix shared by two- and three-way actuators, which render
# identically: not on/off-able (no power state), a FriendlyState headline,
# and a position percentage.
ACTUATOR_DEVICE_TYPE_PREFIX = "actuator"

# Actuator status fields, pushed keyed by the device's UUID.
ACTUATOR_FRIENDLY_STATE_FIELD = "FriendlyState"
ACTUATOR_POSITION_FIELD = "ActualPositionPercentLeft"
CALIBRATED_LEFT_TO_RIGHT_FIELD = "CalibratedMovingLeftToRightTime"
CALIBRATED_RIGHT_TO_LEFT_FIELD = "CalibratedMovingRightToLeftTime"


class ActuatorFriendlyState(StrEnum):
    """An actuator pool device's FriendlyState values."""

    IDLE = "IDLE"
    WAITING_TO_MOVE = "WAITING_TO_MOVE"
    ATTEMPTING_TO_MOVE = "ATTEMPTING_TO_MOVE"
    CALIBRATING = "CALIBRATING"
    OVERLOAD = "OVERLOAD"
    ERROR = "ERROR"
    FAILED = "FAILED"
    OFFLINE = "OFFLINE"


# LIGHT control capabilities pushed by Device.setStatus keyed by the
# control's own UUID, each as a JSON document encoded inside the string
# value rather than as native JSON: the full catalog of named light shows
# and static colors it can be set to via LightName, whether it is dimmable
# at all, and which Brightness percent levels it accepts (empty when not
# dimmable or unconstrained).
AVAILABLE_SHOWS_FIELD = "AvailableShows"
AVAILABLE_COLORS_FIELD = "AvailableColors"
SUPPORTS_BRIGHTNESS_FIELD = "SupportsBrightness"
BRIGHTNESS_INCREMENTS_FIELD = "BrightnessIncrements"
