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


class GroupKind(StrEnum):
    """The Kind of a Site.getControlLayout group."""

    BODY_OF_WATER = "BODY_OF_WATER"
    LANDSCAPE = "LANDSCAPE"


class ControlMode(StrEnum):
    """Valid values for a TEMPERATURE control's ControlMode field."""

    AUTO = "AUTO"
    HEAT = "HEAT"
    COOL = "COOL"


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
CONTROL_MODES_SUPPORTED_FIELD = "ControlModesSupported"

# Body-of-water status items (Device.setStatus, keyed by BodyOfWaterUUID)
CURRENT_TEMPERATURE_FIELD = "Temperature"

# Site-level status item (Device.setStatus, keyed by the site UUID from
# Site.getControlLayout). Changes whenever the attendant's site configuration
# is edited - a signal to re-fetch the control layout and reload the entry.
LAST_TIME_SITE_WAS_LOADED_FIELD = "LastTimeSiteWasLoaded"

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

# Per-control desired-state fields. Not (yet, as far as observed) pushed by
# Device.setStatus; tracked optimistically from our own successful
# Device.setDesiredState2 writes instead.
SET_POINT_FIELD = "SetPoint"
CONTROL_MODE_FIELD = "ControlMode"
POWER_LEVEL_FIELD = "PowerLevel"
BRIGHTNESS_FIELD = "Brightness"
LIGHT_NAME_FIELD = "LightName"
SPEED_FIELD = "Speed"
TWINKLE_FIELD = "Twinkle"
