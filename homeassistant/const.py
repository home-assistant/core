"""Constants used by Home Assistant components."""

from __future__ import annotations

from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING, Final

from .helpers.deprecation import (
    DeprecatedConstant,
    DeprecatedConstantEnum,
    EnumWithDeprecatedMembers,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from .util.event_type import EventType
from .util.hass_dict import HassKey
from .util.signal_type import SignalType

if TYPE_CHECKING:
    from .core import EventStateChangedData, EventStateReportedData
    from .helpers.typing import NoEventData

APPLICATION_NAME: Final = "HomeAssistant"
MAJOR_VERSION: Final = 2025
MINOR_VERSION: Final = 5
PATCH_VERSION: Final = "0b6"
__short_version__: Final = f"{MAJOR_VERSION}.{MINOR_VERSION}"
__version__: Final = f"{__short_version__}.{PATCH_VERSION}"
REQUIRED_PYTHON_VER: Final[tuple[int, int, int]] = (3, 13, 2)
REQUIRED_NEXT_PYTHON_VER: Final[tuple[int, int, int]] = (3, 13, 2)
# Truthy date string triggers showing related deprecation warning messages.
REQUIRED_NEXT_PYTHON_HA_RELEASE: Final = ""

# Format for platform files
PLATFORM_FORMAT: Final = "{platform}.{domain}"


class Platform(StrEnum):
    """Available entity platforms."""

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
    VALVE = "valve"
    WAKE_WORD = "wake_word"
    WATER_HEATER = "water_heater"
    WEATHER = "weather"


BASE_PLATFORMS: Final = {platform.value for platform in Platform}


# Can be used to specify a catch all when registering state or event listeners.
MATCH_ALL: Final = "*"

# Entity target all constant
ENTITY_MATCH_NONE: Final = "none"
ENTITY_MATCH_ALL: Final = "all"
ENTITY_MATCH_ANY: Final = "any"

# If no name is specified
DEVICE_DEFAULT_NAME: Final = "Unnamed Device"

# Max characters for data stored in the recorder (changes to these limits would require
# a database migration)
MAX_LENGTH_EVENT_EVENT_TYPE: Final = 64
MAX_LENGTH_EVENT_ORIGIN: Final = 32
MAX_LENGTH_EVENT_CONTEXT_ID: Final = 36
MAX_LENGTH_STATE_DOMAIN: Final = 64
MAX_LENGTH_STATE_ENTITY_ID: Final = 255
MAX_LENGTH_STATE_STATE: Final = 255

# Sun events
SUN_EVENT_SUNSET: Final = "sunset"
SUN_EVENT_SUNRISE: Final = "sunrise"

# #### CONFIG ####
CONF_ABOVE: Final = "above"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_ACTION: Final = "action"
CONF_ACTIONS: Final = "actions"
CONF_ADDRESS: Final = "address"
CONF_AFTER: Final = "after"
CONF_ALIAS: Final = "alias"
CONF_LLM_HASS_API = "llm_hass_api"
CONF_ALLOWLIST_EXTERNAL_URLS: Final = "allowlist_external_urls"
CONF_API_KEY: Final = "api_key"
CONF_API_TOKEN: Final = "api_token"
CONF_API_VERSION: Final = "api_version"
CONF_ARMING_TIME: Final = "arming_time"
CONF_AT: Final = "at"
CONF_ATTRIBUTE: Final = "attribute"
CONF_AUTH_MFA_MODULES: Final = "auth_mfa_modules"
CONF_AUTH_PROVIDERS: Final = "auth_providers"
CONF_AUTHENTICATION: Final = "authentication"
CONF_BASE: Final = "base"
CONF_BEFORE: Final = "before"
CONF_BELOW: Final = "below"
CONF_BINARY_SENSORS: Final = "binary_sensors"
CONF_BRIGHTNESS: Final = "brightness"
CONF_BROADCAST_ADDRESS: Final = "broadcast_address"
CONF_BROADCAST_PORT: Final = "broadcast_port"
CONF_CHOOSE: Final = "choose"
CONF_CLIENT_ID: Final = "client_id"
CONF_CLIENT_SECRET: Final = "client_secret"
CONF_CODE: Final = "code"
CONF_COLOR_TEMP: Final = "color_temp"
CONF_COMMAND: Final = "command"
CONF_COMMAND_CLOSE: Final = "command_close"
CONF_COMMAND_OFF: Final = "command_off"
CONF_COMMAND_ON: Final = "command_on"
CONF_COMMAND_OPEN: Final = "command_open"
CONF_COMMAND_STATE: Final = "command_state"
CONF_COMMAND_STOP: Final = "command_stop"
CONF_CONDITION: Final = "condition"
CONF_CONDITIONS: Final = "conditions"
CONF_CONTINUE_ON_ERROR: Final = "continue_on_error"
CONF_CONTINUE_ON_TIMEOUT: Final = "continue_on_timeout"
CONF_COUNT: Final = "count"
CONF_COUNTRY: Final = "country"
CONF_COUNTRY_CODE: Final = "country_code"
CONF_COVERS: Final = "covers"
CONF_CURRENCY: Final = "currency"
CONF_CUSTOMIZE: Final = "customize"
CONF_CUSTOMIZE_DOMAIN: Final = "customize_domain"
CONF_CUSTOMIZE_GLOB: Final = "customize_glob"
CONF_DEFAULT: Final = "default"
CONF_DELAY: Final = "delay"
CONF_DELAY_TIME: Final = "delay_time"
CONF_DESCRIPTION: Final = "description"
CONF_DEVICE: Final = "device"
CONF_DEVICES: Final = "devices"
CONF_DEVICE_CLASS: Final = "device_class"
CONF_DEVICE_ID: Final = "device_id"
CONF_DISARM_AFTER_TRIGGER: Final = "disarm_after_trigger"
CONF_DISCOVERY: Final = "discovery"
CONF_DISKS: Final = "disks"
CONF_DISPLAY_CURRENCY: Final = "display_currency"
CONF_DISPLAY_OPTIONS: Final = "display_options"
CONF_DOMAIN: Final = "domain"
CONF_DOMAINS: Final = "domains"
CONF_EFFECT: Final = "effect"
CONF_ELEVATION: Final = "elevation"
CONF_ELSE: Final = "else"
CONF_EMAIL: Final = "email"
CONF_ENABLED: Final = "enabled"
CONF_ENTITIES: Final = "entities"
CONF_ENTITY_CATEGORY: Final = "entity_category"
CONF_ENTITY_ID: Final = "entity_id"
CONF_ENTITY_NAMESPACE: Final = "entity_namespace"
CONF_ENTITY_PICTURE_TEMPLATE: Final = "entity_picture_template"
CONF_ERROR: Final = "error"
CONF_EVENT: Final = "event"
CONF_EVENT_DATA: Final = "event_data"
CONF_EVENT_DATA_TEMPLATE: Final = "event_data_template"
CONF_EXCLUDE: Final = "exclude"
CONF_EXTERNAL_URL: Final = "external_url"
CONF_FILENAME: Final = "filename"
CONF_FILE_PATH: Final = "file_path"
CONF_FOR: Final = "for"
CONF_FOR_EACH: Final = "for_each"
CONF_FORCE_UPDATE: Final = "force_update"
CONF_FRIENDLY_NAME: Final = "friendly_name"
CONF_FRIENDLY_NAME_TEMPLATE: Final = "friendly_name_template"
CONF_HEADERS: Final = "headers"
CONF_HOST: Final = "host"
CONF_HOSTS: Final = "hosts"
CONF_HS: Final = "hs"
CONF_ICON: Final = "icon"
CONF_ICON_TEMPLATE: Final = "icon_template"
CONF_ID: Final = "id"
CONF_IF: Final = "if"
CONF_INCLUDE: Final = "include"
CONF_INTERNAL_URL: Final = "internal_url"
CONF_IP_ADDRESS: Final = "ip_address"
CONF_LANGUAGE: Final = "language"
CONF_LATITUDE: Final = "latitude"
CONF_LEGACY_TEMPLATES: Final = "legacy_templates"
CONF_LIGHTS: Final = "lights"
CONF_LOCATION: Final = "location"
CONF_LONGITUDE: Final = "longitude"
CONF_MAC: Final = "mac"
CONF_MATCH: Final = "match"
CONF_MAXIMUM: Final = "maximum"
CONF_MEDIA_DIRS: Final = "media_dirs"
CONF_METHOD: Final = "method"
CONF_MINIMUM: Final = "minimum"
CONF_MODE: Final = "mode"
CONF_MODEL: Final = "model"
CONF_MODEL_ID: Final = "model_id"
CONF_MONITORED_CONDITIONS: Final = "monitored_conditions"
CONF_MONITORED_VARIABLES: Final = "monitored_variables"
CONF_NAME: Final = "name"
CONF_OFFSET: Final = "offset"
CONF_OPTIMISTIC: Final = "optimistic"
CONF_PACKAGES: Final = "packages"
CONF_PARALLEL: Final = "parallel"
CONF_PARAMS: Final = "params"
CONF_PASSWORD: Final = "password"
CONF_PATH: Final = "path"
CONF_PAYLOAD: Final = "payload"
CONF_PAYLOAD_OFF: Final = "payload_off"
CONF_PAYLOAD_ON: Final = "payload_on"
CONF_PENDING_TIME: Final = "pending_time"
CONF_PIN: Final = "pin"
CONF_PLATFORM: Final = "platform"
CONF_PORT: Final = "port"
CONF_PREFIX: Final = "prefix"
CONF_PROFILE_NAME: Final = "profile_name"
CONF_PROTOCOL: Final = "protocol"
CONF_PROXY_SSL: Final = "proxy_ssl"
CONF_QUOTE: Final = "quote"
CONF_RADIUS: Final = "radius"
CONF_RECIPIENT: Final = "recipient"
CONF_REGION: Final = "region"
CONF_REPEAT: Final = "repeat"
CONF_RESOURCE: Final = "resource"
CONF_RESOURCE_TEMPLATE: Final = "resource_template"
CONF_RESOURCES: Final = "resources"
CONF_RESPONSE_VARIABLE: Final = "response_variable"
CONF_RGB: Final = "rgb"
CONF_ROOM: Final = "room"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_SCENE: Final = "scene"
CONF_SELECTOR: Final = "selector"
CONF_SENDER: Final = "sender"
CONF_SENSORS: Final = "sensors"
CONF_SENSOR_TYPE: Final = "sensor_type"
CONF_SEQUENCE: Final = "sequence"
CONF_SERVICE: Final = "service"
CONF_SERVICE_DATA: Final = "data"
CONF_SERVICE_DATA_TEMPLATE: Final = "data_template"
CONF_SERVICE_TEMPLATE: Final = "service_template"
CONF_SET_CONVERSATION_RESPONSE: Final = "set_conversation_response"
CONF_SHOW_ON_MAP: Final = "show_on_map"
CONF_SLAVE: Final = "slave"
CONF_SOURCE: Final = "source"
CONF_SSL: Final = "ssl"
CONF_STATE: Final = "state"
CONF_STATE_TEMPLATE: Final = "state_template"
CONF_STOP: Final = "stop"
CONF_STRUCTURE: Final = "structure"
CONF_SWITCHES: Final = "switches"
CONF_TARGET: Final = "target"
CONF_TEMPERATURE_UNIT: Final = "temperature_unit"
CONF_THEN: Final = "then"
CONF_TIMEOUT: Final = "timeout"
CONF_TIME_ZONE: Final = "time_zone"
CONF_TOKEN: Final = "token"
CONF_TRIGGER: Final = "trigger"
CONF_TRIGGERS: Final = "triggers"
CONF_TRIGGER_TIME: Final = "trigger_time"
CONF_TTL: Final = "ttl"
CONF_TYPE: Final = "type"
CONF_UNIQUE_ID: Final = "unique_id"
CONF_UNIT_OF_MEASUREMENT: Final = "unit_of_measurement"
CONF_UNIT_SYSTEM: Final = "unit_system"
CONF_UNTIL: Final = "until"
CONF_URL: Final = "url"
CONF_USERNAME: Final = "username"
CONF_UUID: Final = "uuid"
CONF_VALUE_TEMPLATE: Final = "value_template"
CONF_VARIABLES: Final = "variables"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_WAIT_FOR_TRIGGER: Final = "wait_for_trigger"
CONF_WAIT_TEMPLATE: Final = "wait_template"
CONF_WEBHOOK_ID: Final = "webhook_id"
CONF_WEEKDAY: Final = "weekday"
CONF_WHILE: Final = "while"
CONF_WHITELIST: Final = "whitelist"
CONF_ALLOWLIST_EXTERNAL_DIRS: Final = "allowlist_external_dirs"
LEGACY_CONF_WHITELIST_EXTERNAL_DIRS: Final = "whitelist_external_dirs"
CONF_DEBUG: Final = "debug"
CONF_XY: Final = "xy"
CONF_ZONE: Final = "zone"

# #### EVENTS ####
EVENT_CALL_SERVICE: Final = "call_service"
EVENT_COMPONENT_LOADED: Final = "component_loaded"
EVENT_CORE_CONFIG_UPDATE: Final = "core_config_updated"
EVENT_HOMEASSISTANT_CLOSE: EventType[NoEventData] = EventType("homeassistant_close")
EVENT_HOMEASSISTANT_START: EventType[NoEventData] = EventType("homeassistant_start")
EVENT_HOMEASSISTANT_STARTED: EventType[NoEventData] = EventType("homeassistant_started")
EVENT_HOMEASSISTANT_STOP: EventType[NoEventData] = EventType("homeassistant_stop")
EVENT_HOMEASSISTANT_FINAL_WRITE: EventType[NoEventData] = EventType(
    "homeassistant_final_write"
)
EVENT_LOGBOOK_ENTRY: Final = "logbook_entry"
EVENT_LOGGING_CHANGED: Final = "logging_changed"
EVENT_SERVICE_REGISTERED: Final = "service_registered"
EVENT_SERVICE_REMOVED: Final = "service_removed"
EVENT_STATE_CHANGED: EventType[EventStateChangedData] = EventType("state_changed")
EVENT_STATE_REPORTED: EventType[EventStateReportedData] = EventType("state_reported")
EVENT_THEMES_UPDATED: Final = "themes_updated"
EVENT_PANELS_UPDATED: Final = "panels_updated"
EVENT_LOVELACE_UPDATED: Final = "lovelace_updated"
EVENT_RECORDER_5MIN_STATISTICS_GENERATED: Final = "recorder_5min_statistics_generated"
EVENT_RECORDER_HOURLY_STATISTICS_GENERATED: Final = (
    "recorder_hourly_statistics_generated"
)
EVENT_SHOPPING_LIST_UPDATED: Final = "shopping_list_updated"


# #### STATES ####
STATE_ON: Final = "on"
STATE_OFF: Final = "off"
STATE_HOME: Final = "home"
STATE_NOT_HOME: Final = "not_home"
STATE_UNKNOWN: Final = "unknown"
STATE_OPEN: Final = "open"
STATE_OPENING: Final = "opening"
STATE_CLOSED: Final = "closed"
STATE_CLOSING: Final = "closing"
STATE_BUFFERING: Final = "buffering"
STATE_PLAYING: Final = "playing"
STATE_PAUSED: Final = "paused"
STATE_IDLE: Final = "idle"
STATE_STANDBY: Final = "standby"
STATE_UNAVAILABLE: Final = "unavailable"
STATE_OK: Final = "ok"
STATE_PROBLEM: Final = "problem"

# #### LOCK STATES ####
# STATE_* below are deprecated as of 2024.10
# use the LockState enum instead.
_DEPRECATED_STATE_LOCKED: Final = DeprecatedConstant(
    "locked",
    "LockState.LOCKED",
    "2025.10",
)
_DEPRECATED_STATE_UNLOCKED: Final = DeprecatedConstant(
    "unlocked",
    "LockState.UNLOCKED",
    "2025.10",
)
_DEPRECATED_STATE_LOCKING: Final = DeprecatedConstant(
    "locking",
    "LockState.LOCKING",
    "2025.10",
)
_DEPRECATED_STATE_UNLOCKING: Final = DeprecatedConstant(
    "unlocking",
    "LockState.UNLOCKING",
    "2025.10",
)
_DEPRECATED_STATE_JAMMED: Final = DeprecatedConstant(
    "jammed",
    "LockState.JAMMED",
    "2025.10",
)

# #### ALARM CONTROL PANEL STATES ####
# STATE_ALARM_* below are deprecated as of 2024.11
# use the AlarmControlPanelState enum instead.
_DEPRECATED_STATE_ALARM_DISARMED: Final = DeprecatedConstant(
    "disarmed",
    "AlarmControlPanelState.DISARMED",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_ARMED_HOME: Final = DeprecatedConstant(
    "armed_home",
    "AlarmControlPanelState.ARMED_HOME",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_ARMED_AWAY: Final = DeprecatedConstant(
    "armed_away",
    "AlarmControlPanelState.ARMED_AWAY",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_ARMED_NIGHT: Final = DeprecatedConstant(
    "armed_night",
    "AlarmControlPanelState.ARMED_NIGHT",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_ARMED_VACATION: Final = DeprecatedConstant(
    "armed_vacation",
    "AlarmControlPanelState.ARMED_VACATION",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_ARMED_CUSTOM_BYPASS: Final = DeprecatedConstant(
    "armed_custom_bypass",
    "AlarmControlPanelState.ARMED_CUSTOM_BYPASS",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_PENDING: Final = DeprecatedConstant(
    "pending",
    "AlarmControlPanelState.PENDING",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_ARMING: Final = DeprecatedConstant(
    "arming",
    "AlarmControlPanelState.ARMING",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_DISARMING: Final = DeprecatedConstant(
    "disarming",
    "AlarmControlPanelState.DISARMING",
    "2025.11",
)
_DEPRECATED_STATE_ALARM_TRIGGERED: Final = DeprecatedConstant(
    "triggered",
    "AlarmControlPanelState.TRIGGERED",
    "2025.11",
)

# #### STATE AND EVENT ATTRIBUTES ####
# Attribution
ATTR_ATTRIBUTION: Final = "attribution"

# Credentials
ATTR_CREDENTIALS: Final = "credentials"

# Contains time-related attributes
ATTR_NOW: Final = "now"
ATTR_DATE: Final = "date"
ATTR_TIME: Final = "time"
ATTR_SECONDS: Final = "seconds"

# Contains domain, service for a SERVICE_CALL event
ATTR_DOMAIN: Final = "domain"
ATTR_SERVICE: Final = "service"
ATTR_SERVICE_DATA: Final = "service_data"

# IDs
ATTR_ID: Final = "id"

# Name
ATTR_NAME: Final = "name"

# Contains one string or a list of strings, each being an entity id
ATTR_ENTITY_ID: Final = "entity_id"

# Contains one string or a list of strings, each being an area id
ATTR_AREA_ID: Final = "area_id"

# Contains one string, the device ID
ATTR_DEVICE_ID: Final = "device_id"

# Contains one string or a list of strings, each being an floor id
ATTR_FLOOR_ID: Final = "floor_id"

# Contains one string or a list of strings, each being an label id
ATTR_LABEL_ID: Final = "label_id"

# String with a friendly name for the entity
ATTR_FRIENDLY_NAME: Final = "friendly_name"

# A picture to represent entity
ATTR_ENTITY_PICTURE: Final = "entity_picture"

ATTR_IDENTIFIERS: Final = "identifiers"

# Icon to use in the frontend
ATTR_ICON: Final = "icon"

# The unit of measurement if applicable
ATTR_UNIT_OF_MEASUREMENT: Final = "unit_of_measurement"

CONF_UNIT_SYSTEM_METRIC: Final = "metric"
"""Deprecated: please use a local constant."""
CONF_UNIT_SYSTEM_IMPERIAL: Final = "imperial"
"""Deprecated: please use a local constant."""

# Electrical attributes
ATTR_VOLTAGE: Final = "voltage"

# Location of the device/sensor
ATTR_LOCATION: Final = "location"

ATTR_MODE: Final = "mode"

ATTR_CONFIGURATION_URL: Final = "configuration_url"
ATTR_CONNECTIONS: Final = "connections"
ATTR_DEFAULT_NAME: Final = "default_name"
ATTR_MANUFACTURER: Final = "manufacturer"
ATTR_MODEL: Final = "model"
ATTR_MODEL_ID: Final = "model_id"
ATTR_SERIAL_NUMBER: Final = "serial_number"
ATTR_SUGGESTED_AREA: Final = "suggested_area"
ATTR_SW_VERSION: Final = "sw_version"
ATTR_HW_VERSION: Final = "hw_version"
ATTR_VIA_DEVICE: Final = "via_device"

ATTR_BATTERY_CHARGING: Final = "battery_charging"
ATTR_BATTERY_LEVEL: Final = "battery_level"
ATTR_WAKEUP: Final = "wake_up_interval"

# For devices which support a code attribute
ATTR_CODE: Final = "code"
ATTR_CODE_FORMAT: Final = "code_format"

# For calling a device specific command
ATTR_COMMAND: Final = "command"

# For devices which support an armed state
ATTR_ARMED: Final = "device_armed"

# For devices which support a locked state
ATTR_LOCKED: Final = "locked"

# For sensors that support 'tripping', eg. motion and door sensors
ATTR_TRIPPED: Final = "device_tripped"

# For sensors that support 'tripping' this holds the most recent
# time the device was tripped
ATTR_LAST_TRIP_TIME: Final = "last_tripped_time"

# For all entity's, this hold whether or not it should be hidden
ATTR_HIDDEN: Final = "hidden"

# Location of the entity
ATTR_LATITUDE: Final = "latitude"
ATTR_LONGITUDE: Final = "longitude"

# Elevation of the entity
ATTR_ELEVATION: Final = "elevation"

# Accuracy of location in meters
ATTR_GPS_ACCURACY: Final = "gps_accuracy"

# If state is assumed
ATTR_ASSUMED_STATE: Final = "assumed_state"
ATTR_STATE: Final = "state"

ATTR_EDITABLE: Final = "editable"
ATTR_OPTION: Final = "option"

# The entity has been restored with restore state
ATTR_RESTORED: Final = "restored"

# Bitfield of supported component features for the entity
ATTR_SUPPORTED_FEATURES: Final = "supported_features"

# Class of device within its domain
ATTR_DEVICE_CLASS: Final = "device_class"

# Temperature attribute
ATTR_TEMPERATURE: Final = "temperature"

# Persons attribute
ATTR_PERSONS: Final = "persons"


# #### UNITS OF MEASUREMENT ####
# Apparent power units
class UnitOfApparentPower(StrEnum):
    """Apparent power units."""

    VOLT_AMPERE = "VA"


# Power units
class UnitOfPower(StrEnum):
    """Power units."""

    MILLIWATT = "mW"
    WATT = "W"
    KILO_WATT = "kW"
    MEGA_WATT = "MW"
    GIGA_WATT = "GW"
    TERA_WATT = "TW"
    BTU_PER_HOUR = "BTU/h"


# Reactive power units
class UnitOfReactivePower(StrEnum):
    """Reactive power units."""

    VOLT_AMPERE_REACTIVE = "var"
    KILO_VOLT_AMPERE_REACTIVE = "kvar"


_DEPRECATED_POWER_VOLT_AMPERE_REACTIVE: Final = DeprecatedConstantEnum(
    UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    "2025.9",
)
"""Deprecated: please use UnitOfReactivePower.VOLT_AMPERE_REACTIVE."""


# Energy units
class UnitOfEnergy(StrEnum):
    """Energy units."""

    JOULE = "J"
    KILO_JOULE = "kJ"
    MEGA_JOULE = "MJ"
    GIGA_JOULE = "GJ"
    MILLIWATT_HOUR = "mWh"
    WATT_HOUR = "Wh"
    KILO_WATT_HOUR = "kWh"
    MEGA_WATT_HOUR = "MWh"
    GIGA_WATT_HOUR = "GWh"
    TERA_WATT_HOUR = "TWh"
    CALORIE = "cal"
    KILO_CALORIE = "kcal"
    MEGA_CALORIE = "Mcal"
    GIGA_CALORIE = "Gcal"


# Energy Distance units
class UnitOfEnergyDistance(StrEnum):
    """Energy Distance units."""

    KILO_WATT_HOUR_PER_100_KM = "kWh/100km"
    MILES_PER_KILO_WATT_HOUR = "mi/kWh"
    KM_PER_KILO_WATT_HOUR = "km/kWh"


# Electric_current units
class UnitOfElectricCurrent(StrEnum):
    """Electric current units."""

    MILLIAMPERE = "mA"
    AMPERE = "A"


# Electric_potential units
class UnitOfElectricPotential(StrEnum):
    """Electric potential units."""

    MICROVOLT = "µV"
    MILLIVOLT = "mV"
    VOLT = "V"
    KILOVOLT = "kV"
    MEGAVOLT = "MV"


# Degree units
DEGREE: Final = "°"

# Currency units
CURRENCY_EURO: Final = "€"
CURRENCY_DOLLAR: Final = "$"
CURRENCY_CENT: Final = "¢"


# Temperature units
class UnitOfTemperature(StrEnum):
    """Temperature units."""

    CELSIUS = "°C"
    FAHRENHEIT = "°F"
    KELVIN = "K"


# Time units
class UnitOfTime(StrEnum):
    """Time units."""

    MICROSECONDS = "μs"
    MILLISECONDS = "ms"
    SECONDS = "s"
    MINUTES = "min"
    HOURS = "h"
    DAYS = "d"
    WEEKS = "w"
    MONTHS = "m"
    YEARS = "y"


# Length units
class UnitOfLength(StrEnum):
    """Length units."""

    MILLIMETERS = "mm"
    CENTIMETERS = "cm"
    METERS = "m"
    KILOMETERS = "km"
    INCHES = "in"
    FEET = "ft"
    YARDS = "yd"
    MILES = "mi"
    NAUTICAL_MILES = "nmi"


# Frequency units
class UnitOfFrequency(StrEnum):
    """Frequency units."""

    HERTZ = "Hz"
    KILOHERTZ = "kHz"
    MEGAHERTZ = "MHz"
    GIGAHERTZ = "GHz"


# Pressure units
class UnitOfPressure(StrEnum):
    """Pressure units."""

    PA = "Pa"
    HPA = "hPa"
    KPA = "kPa"
    BAR = "bar"
    CBAR = "cbar"
    MBAR = "mbar"
    MMHG = "mmHg"
    INHG = "inHg"
    PSI = "psi"


# Sound pressure units
class UnitOfSoundPressure(StrEnum):
    """Sound pressure units."""

    DECIBEL = "dB"
    WEIGHTED_DECIBEL_A = "dBA"


# Volume units
class UnitOfVolume(StrEnum):
    """Volume units."""

    CUBIC_FEET = "ft³"
    CENTUM_CUBIC_FEET = "CCF"
    CUBIC_METERS = "m³"
    LITERS = "L"
    MILLILITERS = "mL"
    GALLONS = "gal"
    """Assumed to be US gallons in conversion utilities.

    British/Imperial gallons are not yet supported"""
    FLUID_OUNCES = "fl. oz."
    """Assumed to be US fluid ounces in conversion utilities.

    British/Imperial fluid ounces are not yet supported"""


# Volume Flow Rate units
class UnitOfVolumeFlowRate(StrEnum):
    """Volume flow rate units."""

    CUBIC_METERS_PER_HOUR = "m³/h"
    CUBIC_METERS_PER_SECOND = "m³/s"
    CUBIC_FEET_PER_MINUTE = "ft³/min"
    LITERS_PER_HOUR = "L/h"
    LITERS_PER_MINUTE = "L/min"
    LITERS_PER_SECOND = "L/s"
    GALLONS_PER_MINUTE = "gal/min"
    MILLILITERS_PER_SECOND = "mL/s"


class UnitOfArea(StrEnum):
    """Area units."""

    SQUARE_METERS = "m²"
    SQUARE_CENTIMETERS = "cm²"
    SQUARE_KILOMETERS = "km²"
    SQUARE_MILLIMETERS = "mm²"
    SQUARE_INCHES = "in²"
    SQUARE_FEET = "ft²"
    SQUARE_YARDS = "yd²"
    SQUARE_MILES = "mi²"
    ACRES = "ac"
    HECTARES = "ha"


_DEPRECATED_AREA_SQUARE_METERS: Final = DeprecatedConstantEnum(
    UnitOfArea.SQUARE_METERS,
    "2025.12",
)
"""Deprecated: please use UnitOfArea.SQUARE_METERS"""


# Mass units
class UnitOfMass(StrEnum):
    """Mass units."""

    GRAMS = "g"
    KILOGRAMS = "kg"
    MILLIGRAMS = "mg"
    MICROGRAMS = "µg"
    OUNCES = "oz"
    POUNDS = "lb"
    STONES = "st"


class UnitOfConductivity(
    StrEnum,
    metaclass=EnumWithDeprecatedMembers,
    deprecated={
        "SIEMENS": ("UnitOfConductivity.SIEMENS_PER_CM", "2025.11.0"),
        "MICROSIEMENS": ("UnitOfConductivity.MICROSIEMENS_PER_CM", "2025.11.0"),
        "MILLISIEMENS": ("UnitOfConductivity.MILLISIEMENS_PER_CM", "2025.11.0"),
    },
):
    """Conductivity units."""

    SIEMENS_PER_CM = "S/cm"
    MICROSIEMENS_PER_CM = "µS/cm"
    MILLISIEMENS_PER_CM = "mS/cm"

    # Deprecated aliases
    SIEMENS = "S/cm"
    """Deprecated: Please use UnitOfConductivity.SIEMENS_PER_CM"""
    MICROSIEMENS = "µS/cm"
    """Deprecated: Please use UnitOfConductivity.MICROSIEMENS_PER_CM"""
    MILLISIEMENS = "mS/cm"
    """Deprecated: Please use UnitOfConductivity.MILLISIEMENS_PER_CM"""


_DEPRECATED_CONDUCTIVITY: Final = DeprecatedConstantEnum(
    UnitOfConductivity.MICROSIEMENS_PER_CM,
    "2025.11",
)
"""Deprecated: please use UnitOfConductivity.MICROSIEMENS_PER_CM"""

# Light units
LIGHT_LUX: Final = "lx"

# UV Index units
UV_INDEX: Final = "UV index"

# Percentage units
PERCENTAGE: Final = "%"

# Rotational speed units
REVOLUTIONS_PER_MINUTE: Final = "rpm"


# Irradiance units
class UnitOfIrradiance(StrEnum):
    """Irradiance units."""

    WATTS_PER_SQUARE_METER = "W/m²"
    BTUS_PER_HOUR_SQUARE_FOOT = "BTU/(h⋅ft²)"


class UnitOfVolumetricFlux(StrEnum):
    """Volumetric flux, commonly used for precipitation intensity.

    The derivation of these units is a volume of rain amassing in a container
    with constant cross section in a given time
    """

    INCHES_PER_DAY = "in/d"
    """Derived from in³/(in²⋅d)"""

    INCHES_PER_HOUR = "in/h"
    """Derived from in³/(in²⋅h)"""

    MILLIMETERS_PER_DAY = "mm/d"
    """Derived from mm³/(mm²⋅d)"""

    MILLIMETERS_PER_HOUR = "mm/h"
    """Derived from mm³/(mm²⋅h)"""


class UnitOfPrecipitationDepth(StrEnum):
    """Precipitation depth.

    The derivation of these units is a volume of rain amassing in a container
    with constant cross section
    """

    INCHES = "in"
    """Derived from in³/in²"""

    MILLIMETERS = "mm"
    """Derived from mm³/mm²"""

    CENTIMETERS = "cm"
    """Derived from cm³/cm²"""


# Concentration units
CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "µg/m³"
CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER: Final = "mg/m³"
CONCENTRATION_MICROGRAMS_PER_CUBIC_FOOT: Final = "μg/ft³"
CONCENTRATION_PARTS_PER_CUBIC_METER: Final = "p/m³"
CONCENTRATION_PARTS_PER_MILLION: Final = "ppm"
CONCENTRATION_PARTS_PER_BILLION: Final = "ppb"


class UnitOfBloodGlucoseConcentration(StrEnum):
    """Blood glucose concentration units."""

    MILLIGRAMS_PER_DECILITER = "mg/dL"
    MILLIMOLE_PER_LITER = "mmol/L"


# Speed units
class UnitOfSpeed(StrEnum):
    """Speed units."""

    BEAUFORT = "Beaufort"
    FEET_PER_SECOND = "ft/s"
    INCHES_PER_SECOND = "in/s"
    METERS_PER_SECOND = "m/s"
    KILOMETERS_PER_HOUR = "km/h"
    KNOTS = "kn"
    MILES_PER_HOUR = "mph"
    MILLIMETERS_PER_SECOND = "mm/s"


# Signal_strength units
SIGNAL_STRENGTH_DECIBELS: Final = "dB"
SIGNAL_STRENGTH_DECIBELS_MILLIWATT: Final = "dBm"


# Data units
class UnitOfInformation(StrEnum):
    """Information units."""

    BITS = "bit"
    KILOBITS = "kbit"
    MEGABITS = "Mbit"
    GIGABITS = "Gbit"
    BYTES = "B"
    KILOBYTES = "kB"
    MEGABYTES = "MB"
    GIGABYTES = "GB"
    TERABYTES = "TB"
    PETABYTES = "PB"
    EXABYTES = "EB"
    ZETTABYTES = "ZB"
    YOTTABYTES = "YB"
    KIBIBYTES = "KiB"
    MEBIBYTES = "MiB"
    GIBIBYTES = "GiB"
    TEBIBYTES = "TiB"
    PEBIBYTES = "PiB"
    EXBIBYTES = "EiB"
    ZEBIBYTES = "ZiB"
    YOBIBYTES = "YiB"


# Data_rate units
class UnitOfDataRate(StrEnum):
    """Data rate units."""

    BITS_PER_SECOND = "bit/s"
    KILOBITS_PER_SECOND = "kbit/s"
    MEGABITS_PER_SECOND = "Mbit/s"
    GIGABITS_PER_SECOND = "Gbit/s"
    BYTES_PER_SECOND = "B/s"
    KILOBYTES_PER_SECOND = "kB/s"
    MEGABYTES_PER_SECOND = "MB/s"
    GIGABYTES_PER_SECOND = "GB/s"
    KIBIBYTES_PER_SECOND = "KiB/s"
    MEBIBYTES_PER_SECOND = "MiB/s"
    GIBIBYTES_PER_SECOND = "GiB/s"


# States
COMPRESSED_STATE_STATE: Final = "s"
COMPRESSED_STATE_ATTRIBUTES: Final = "a"
COMPRESSED_STATE_CONTEXT: Final = "c"
COMPRESSED_STATE_LAST_CHANGED: Final = "lc"
COMPRESSED_STATE_LAST_UPDATED: Final = "lu"

# #### SERVICES ####
SERVICE_TURN_ON: Final = "turn_on"
SERVICE_TURN_OFF: Final = "turn_off"
SERVICE_TOGGLE: Final = "toggle"
SERVICE_RELOAD: Final = "reload"

SERVICE_VOLUME_UP: Final = "volume_up"
SERVICE_VOLUME_DOWN: Final = "volume_down"
SERVICE_VOLUME_MUTE: Final = "volume_mute"
SERVICE_VOLUME_SET: Final = "volume_set"
SERVICE_MEDIA_PLAY_PAUSE: Final = "media_play_pause"
SERVICE_MEDIA_PLAY: Final = "media_play"
SERVICE_MEDIA_PAUSE: Final = "media_pause"
SERVICE_MEDIA_STOP: Final = "media_stop"
SERVICE_MEDIA_NEXT_TRACK: Final = "media_next_track"
SERVICE_MEDIA_PREVIOUS_TRACK: Final = "media_previous_track"
SERVICE_MEDIA_SEEK: Final = "media_seek"
SERVICE_REPEAT_SET: Final = "repeat_set"
SERVICE_SHUFFLE_SET: Final = "shuffle_set"

SERVICE_ALARM_DISARM: Final = "alarm_disarm"
SERVICE_ALARM_ARM_HOME: Final = "alarm_arm_home"
SERVICE_ALARM_ARM_AWAY: Final = "alarm_arm_away"
SERVICE_ALARM_ARM_NIGHT: Final = "alarm_arm_night"
SERVICE_ALARM_ARM_VACATION: Final = "alarm_arm_vacation"
SERVICE_ALARM_ARM_CUSTOM_BYPASS: Final = "alarm_arm_custom_bypass"
SERVICE_ALARM_TRIGGER: Final = "alarm_trigger"


SERVICE_LOCK: Final = "lock"
SERVICE_UNLOCK: Final = "unlock"

SERVICE_OPEN: Final = "open"
SERVICE_CLOSE: Final = "close"

SERVICE_CLOSE_COVER: Final = "close_cover"
SERVICE_CLOSE_COVER_TILT: Final = "close_cover_tilt"
SERVICE_OPEN_COVER: Final = "open_cover"
SERVICE_OPEN_COVER_TILT: Final = "open_cover_tilt"
SERVICE_SAVE_PERSISTENT_STATES: Final = "save_persistent_states"
SERVICE_SET_COVER_POSITION: Final = "set_cover_position"
SERVICE_SET_COVER_TILT_POSITION: Final = "set_cover_tilt_position"
SERVICE_STOP_COVER: Final = "stop_cover"
SERVICE_STOP_COVER_TILT: Final = "stop_cover_tilt"
SERVICE_TOGGLE_COVER_TILT: Final = "toggle_cover_tilt"

SERVICE_CLOSE_VALVE: Final = "close_valve"
SERVICE_OPEN_VALVE: Final = "open_valve"
SERVICE_SET_VALVE_POSITION: Final = "set_valve_position"
SERVICE_STOP_VALVE: Final = "stop_valve"

SERVICE_SELECT_OPTION: Final = "select_option"

# #### API / REMOTE ####
SERVER_PORT: Final = 8123

URL_ROOT: Final = "/"
URL_API: Final = "/api/"
URL_API_STREAM: Final = "/api/stream"
URL_API_CORE_STATE: Final = "/api/core/state"
URL_API_CONFIG: Final = "/api/config"
URL_API_STATES: Final = "/api/states"
URL_API_STATES_ENTITY: Final = "/api/states/{}"
URL_API_EVENTS: Final = "/api/events"
URL_API_EVENTS_EVENT: Final = "/api/events/{}"
URL_API_SERVICES: Final = "/api/services"
URL_API_SERVICES_SERVICE: Final = "/api/services/{}/{}"
URL_API_COMPONENTS: Final = "/api/components"
URL_API_ERROR_LOG: Final = "/api/error_log"
URL_API_LOG_OUT: Final = "/api/log_out"
URL_API_TEMPLATE: Final = "/api/template"

HTTP_BASIC_AUTHENTICATION: Final = "basic"
HTTP_BEARER_AUTHENTICATION: Final = "bearer_token"
HTTP_DIGEST_AUTHENTICATION: Final = "digest"

HTTP_HEADER_X_REQUESTED_WITH: Final = "X-Requested-With"

CONTENT_TYPE_JSON: Final = "application/json"
CONTENT_TYPE_MULTIPART: Final = "multipart/x-mixed-replace; boundary={}"
CONTENT_TYPE_TEXT_PLAIN: Final = "text/plain"

# The exit code to send to request a restart
RESTART_EXIT_CODE: Final = 100

UNIT_NOT_RECOGNIZED_TEMPLATE: Final = "{} is not a recognized {} unit."

LENGTH: Final = "length"
AREA: Final = "area"
MASS: Final = "mass"
PRESSURE: Final = "pressure"
VOLUME: Final = "volume"
TEMPERATURE: Final = "temperature"
SPEED: Final = "speed"
WIND_SPEED: Final = "wind_speed"
ILLUMINANCE: Final = "illuminance"
ACCUMULATED_PRECIPITATION: Final = "accumulated_precipitation"

WEEKDAYS: Final[list[str]] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# The degree of precision for platforms
PRECISION_WHOLE: Final = 1
PRECISION_HALVES: Final = 0.5
PRECISION_TENTHS: Final = 0.1

# Static list of entities that will never be exposed to
# cloud, alexa, or google_home components
CLOUD_NEVER_EXPOSED_ENTITIES: Final[list[str]] = ["group.all_locks"]


class EntityCategory(StrEnum):
    """Category of an entity.

    An entity with a category will:
    - Not be exposed to cloud, Alexa, or Google Assistant components
    - Not be included in indirect service calls to devices or areas
    """

    # Config: An entity which allows changing the configuration of a device.
    CONFIG = "config"

    # Diagnostic: An entity exposing some configuration parameter,
    # or diagnostics of a device.
    DIAGNOSTIC = "diagnostic"


ENTITY_CATEGORIES: Final[list[str]] = [cls.value for cls in EntityCategory]

# The ID of the Home Assistant Media Player Cast App
CAST_APP_ID_HOMEASSISTANT_MEDIA: Final = "B45F4572"
# The ID of the Home Assistant Lovelace Cast App
CAST_APP_ID_HOMEASSISTANT_LOVELACE: Final = "A078F6B0"

# User used by Supervisor
HASSIO_USER_NAME = "Supervisor"

SIGNAL_BOOTSTRAP_INTEGRATIONS: SignalType[dict[str, float]] = SignalType(
    "bootstrap_integrations"
)


# hass.data key for logging information.
KEY_DATA_LOGGING: HassKey[str] = HassKey("logging")


# Date/Time formats
FORMAT_DATE: Final = "%Y-%m-%d"
FORMAT_TIME: Final = "%H:%M:%S"
FORMAT_DATETIME: Final = f"{FORMAT_DATE} {FORMAT_TIME}"


# Maximum entities expected in the state machine
# This is not a hard limit, but caches and other
# data structures will be pre-allocated to this size
MAX_EXPECTED_ENTITY_IDS: Final = 16384

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
