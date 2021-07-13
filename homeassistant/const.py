from __future__ import annotations

from typing import Final

MAJOR_VERSION: Final = 2021
MINOR_VERSION: Final = 7
PATCH_VERSION: Final = "2b0"
__short_version__: Final = f"{MAJOR_VERSION}.{MINOR_VERSION}"
__version__: Final = f"{__short_version__}.{PATCH_VERSION}"
REQUIRED_PYTHON_VER: Final[tuple[int, int, int]] = (3, 8, 0)
# Truthy date string triggers showing related deprecation warning messages.
REQUIRED_NEXT_PYTHON_VER: Final[tuple[int, int, int]] = (3, 9, 0)
REQUIRED_NEXT_PYTHON_DATE: Final = ""

# Format for platform files
PLATFORM_FORMAT: Final = "{platform}.{domain}"

# Can be used to specify a catch all when registering state or event listeners.
MATCH_ALL: Final = "*"

# Entity target all constant
ENTITY_MATCH_NONE: Final = "none"
ENTITY_MATCH_ALL: Final = "all"

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
CONF_ADDRESS: Final = "address"
CONF_AFTER: Final = "after"
CONF_ALIAS: Final = "alias"
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
CONF_CONTINUE_ON_TIMEOUT: Final = "continue_on_timeout"
CONF_COUNT: Final = "count"
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
CONF_EMAIL: Final = "email"
CONF_ENTITIES: Final = "entities"
CONF_ENTITY_ID: Final = "entity_id"
CONF_ENTITY_NAMESPACE: Final = "entity_namespace"
CONF_ENTITY_PICTURE_TEMPLATE: Final = "entity_picture_template"
CONF_EVENT: Final = "event"
CONF_EVENT_DATA: Final = "event_data"
CONF_EVENT_DATA_TEMPLATE: Final = "event_data_template"
CONF_EXCLUDE: Final = "exclude"
CONF_EXTERNAL_URL: Final = "external_url"
CONF_FILENAME: Final = "filename"
CONF_FILE_PATH: Final = "file_path"
CONF_FOR: Final = "for"
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
CONF_INCLUDE: Final = "include"
CONF_INTERNAL_URL: Final = "internal_url"
CONF_IP_ADDRESS: Final = "ip_address"
CONF_LATITUDE: Final = "latitude"
CONF_LEGACY_TEMPLATES: Final = "legacy_templates"
CONF_LIGHTS: Final = "lights"
CONF_LONGITUDE: Final = "longitude"
CONF_MAC: Final = "mac"
CONF_MAXIMUM: Final = "maximum"
CONF_MEDIA_DIRS: Final = "media_dirs"
CONF_METHOD: Final = "method"
CONF_MINIMUM: Final = "minimum"
CONF_MODE: Final = "mode"
CONF_MONITORED_CONDITIONS: Final = "monitored_conditions"
CONF_MONITORED_VARIABLES: Final = "monitored_variables"
CONF_NAME: Final = "name"
CONF_OFFSET: Final = "offset"
CONF_OPTIMISTIC: Final = "optimistic"
CONF_PACKAGES: Final = "packages"
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
CONF_RESOURCES: Final = "resources"
CONF_RESOURCE_TEMPLATE: Final = "resource_template"
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
CONF_SERVICE_TEMPLATE: Final = "service_template"
CONF_SHOW_ON_MAP: Final = "show_on_map"
CONF_SLAVE: Final = "slave"
CONF_SOURCE: Final = "source"
CONF_SSL: Final = "ssl"
CONF_STATE: Final = "state"
CONF_STATE_TEMPLATE: Final = "state_template"
CONF_STRUCTURE: Final = "structure"
CONF_SWITCHES: Final = "switches"
CONF_TARGET: Final = "target"
CONF_TEMPERATURE_UNIT: Final = "temperature_unit"
CONF_TIMEOUT: Final = "timeout"
CONF_TIME_ZONE: Final = "time_zone"
CONF_TOKEN: Final = "token"
CONF_TRIGGER_TIME: Final = "trigger_time"
CONF_TTL: Final = "ttl"
CONF_TYPE: Final = "type"
CONF_UNIQUE_ID: Final = "unique_id"
CONF_UNIT_OF_MEASUREMENT: Final = "unit_of_measurement"
CONF_UNIT_SYSTEM: Final = "unit_system"
CONF_UNTIL: Final = "until"
CONF_URL: Final = "url"
CONF_USERNAME: Final = "username"
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
CONF_WHITE_VALUE: Final = "white_value"
CONF_XY: Final = "xy"
CONF_ZONE: Final = "zone"

# #### EVENTS ####
EVENT_CALL_SERVICE: Final = "call_service"
EVENT_COMPONENT_LOADED: Final = "component_loaded"
EVENT_CORE_CONFIG_UPDATE: Final = "core_config_updated"
EVENT_HOMEASSISTANT_CLOSE: Final = "homeassistant_close"
EVENT_HOMEASSISTANT_START: Final = "homeassistant_start"
EVENT_HOMEASSISTANT_STARTED: Final = "homeassistant_started"
EVENT_HOMEASSISTANT_STOP: Final = "homeassistant_stop"
EVENT_HOMEASSISTANT_FINAL_WRITE: Final = "homeassistant_final_write"
EVENT_LOGBOOK_ENTRY: Final = "logbook_entry"
EVENT_SERVICE_REGISTERED: Final = "service_registered"
EVENT_SERVICE_REMOVED: Final = "service_removed"
EVENT_STATE_CHANGED: Final = "state_changed"
EVENT_THEMES_UPDATED: Final = "themes_updated"
EVENT_TIMER_OUT_OF_SYNC: Final = "timer_out_of_sync"
EVENT_TIME_CHANGED: Final = "time_changed"


# #### DEVICE CLASSES ####
DEVICE_CLASS_BATTERY: Final = "battery"
DEVICE_CLASS_CO: Final = "carbon_monoxide"
DEVICE_CLASS_CO2: Final = "carbon_dioxide"
DEVICE_CLASS_CURRENT: Final = "current"
DEVICE_CLASS_ENERGY: Final = "energy"
DEVICE_CLASS_HUMIDITY: Final = "humidity"
DEVICE_CLASS_ILLUMINANCE: Final = "illuminance"
DEVICE_CLASS_MONETARY: Final = "monetary"
DEVICE_CLASS_POWER_FACTOR: Final = "power_factor"
DEVICE_CLASS_POWER: Final = "power"
DEVICE_CLASS_PRESSURE: Final = "pressure"
DEVICE_CLASS_SIGNAL_STRENGTH: Final = "signal_strength"
DEVICE_CLASS_TEMPERATURE: Final = "temperature"
DEVICE_CLASS_TIMESTAMP: Final = "timestamp"
DEVICE_CLASS_VOLTAGE: Final = "voltage"

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
STATE_PLAYING: Final = "playing"
STATE_PAUSED: Final = "paused"
STATE_IDLE: Final = "idle"
STATE_STANDBY: Final = "standby"
STATE_ALARM_DISARMED: Final = "disarmed"
STATE_ALARM_ARMED_HOME: Final = "armed_home"
STATE_ALARM_ARMED_AWAY: Final = "armed_away"
STATE_ALARM_ARMED_NIGHT: Final = "armed_night"
STATE_ALARM_ARMED_CUSTOM_BYPASS: Final = "armed_custom_bypass"
STATE_ALARM_PENDING: Final = "pending"
STATE_ALARM_ARMING: Final = "arming"
STATE_ALARM_DISARMING: Final = "disarming"
STATE_ALARM_TRIGGERED: Final = "triggered"
STATE_LOCKED: Final = "locked"
STATE_UNLOCKED: Final = "unlocked"
STATE_UNAVAILABLE: Final = "unavailable"
STATE_OK: Final = "ok"
STATE_PROBLEM: Final = "problem"

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
CONF_UNIT_SYSTEM_IMPERIAL: Final = "imperial"

# Electrical attributes
ATTR_VOLTAGE: Final = "voltage"

# Location of the device/sensor
ATTR_LOCATION: Final = "location"

ATTR_MODE: Final = "mode"

ATTR_MANUFACTURER: Final = "manufacturer"
ATTR_MODEL: Final = "model"
ATTR_SW_VERSION: Final = "sw_version"

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

# #### UNITS OF MEASUREMENT ####
# Power units
POWER_WATT: Final = "W"
POWER_KILO_WATT: Final = "kW"

# Voltage units
VOLT: Final = "V"

# Energy units
ENERGY_WATT_HOUR: Final = "Wh"
ENERGY_KILO_WATT_HOUR: Final = "kWh"

# Electrical units
ELECTRICAL_CURRENT_AMPERE: Final = "A"
ELECTRICAL_VOLT_AMPERE: Final = "VA"

# Degree units
DEGREE: Final = "°"

# Currency units
CURRENCY_EURO: Final = "€"
CURRENCY_DOLLAR: Final = "$"
CURRENCY_CENT: Final = "¢"

# Temperature units
TEMP_CELSIUS: Final = "°C"
TEMP_FAHRENHEIT: Final = "°F"
TEMP_KELVIN: Final = "K"

# Time units
TIME_MICROSECONDS: Final = "μs"
TIME_MILLISECONDS: Final = "ms"
TIME_SECONDS: Final = "s"
TIME_MINUTES: Final = "min"
TIME_HOURS: Final = "h"
TIME_DAYS: Final = "d"
TIME_WEEKS: Final = "w"
TIME_MONTHS: Final = "m"
TIME_YEARS: Final = "y"

# Length units
LENGTH_MILLIMETERS: Final = "mm"
LENGTH_CENTIMETERS: Final = "cm"
LENGTH_METERS: Final = "m"
LENGTH_KILOMETERS: Final = "km"

LENGTH_INCHES: Final = "in"
LENGTH_FEET: Final = "ft"
LENGTH_YARD: Final = "yd"
LENGTH_MILES: Final = "mi"

# Frequency units
FREQUENCY_HERTZ: Final = "Hz"
FREQUENCY_GIGAHERTZ: Final = "GHz"

# Pressure units
PRESSURE_PA: Final = "Pa"
PRESSURE_HPA: Final = "hPa"
PRESSURE_BAR: Final = "bar"
PRESSURE_MBAR: Final = "mbar"
PRESSURE_INHG: Final = "inHg"
PRESSURE_PSI: Final = "psi"

# Volume units
VOLUME_LITERS: Final = "L"
VOLUME_MILLILITERS: Final = "mL"
VOLUME_CUBIC_METERS: Final = "m³"
VOLUME_CUBIC_FEET: Final = "ft³"

VOLUME_GALLONS: Final = "gal"
VOLUME_FLUID_OUNCE: Final = "fl. oz."

# Volume Flow Rate units
VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR: Final = "m³/h"
VOLUME_FLOW_RATE_CUBIC_FEET_PER_MINUTE: Final = "ft³/m"

# Area units
AREA_SQUARE_METERS: Final = "m²"

# Mass units
MASS_GRAMS: Final = "g"
MASS_KILOGRAMS: Final = "kg"
MASS_MILLIGRAMS: Final = "mg"
MASS_MICROGRAMS: Final = "µg"

MASS_OUNCES: Final = "oz"
MASS_POUNDS: Final = "lb"

# Conductivity units
CONDUCTIVITY: Final = "µS/cm"

# Light units
LIGHT_LUX: Final = "lx"

# UV Index units
UV_INDEX: Final = "UV index"

# Percentage units
PERCENTAGE: Final = "%"

# Irradiation units
IRRADIATION_WATTS_PER_SQUARE_METER: Final = "W/m²"
IRRADIATION_BTUS_PER_HOUR_SQUARE_FOOT: Final = "BTU/(h×ft²)"

# Precipitation units
PRECIPITATION_MILLIMETERS_PER_HOUR: Final = "mm/h"

# Concentration units
CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "µg/m³"
CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER: Final = "mg/m³"
CONCENTRATION_MICROGRAMS_PER_CUBIC_FOOT: Final = "μg/ft³"
CONCENTRATION_PARTS_PER_CUBIC_METER: Final = "p/m³"
CONCENTRATION_PARTS_PER_MILLION: Final = "ppm"
CONCENTRATION_PARTS_PER_BILLION: Final = "ppb"

# Speed units
SPEED_MILLIMETERS_PER_DAY: Final = "mm/d"
SPEED_INCHES_PER_DAY: Final = "in/d"
SPEED_METERS_PER_SECOND: Final = "m/s"
SPEED_INCHES_PER_HOUR: Final = "in/h"
SPEED_KILOMETERS_PER_HOUR: Final = "km/h"
SPEED_MILES_PER_HOUR: Final = "mph"

# Signal_strength units
SIGNAL_STRENGTH_DECIBELS: Final = "dB"
SIGNAL_STRENGTH_DECIBELS_MILLIWATT: Final = "dBm"

# Data units
DATA_BITS: Final = "bit"
DATA_KILOBITS: Final = "kbit"
DATA_MEGABITS: Final = "Mbit"
DATA_GIGABITS: Final = "Gbit"
DATA_BYTES: Final = "B"
DATA_KILOBYTES: Final = "kB"
DATA_MEGABYTES: Final = "MB"
DATA_GIGABYTES: Final = "GB"
DATA_TERABYTES: Final = "TB"
DATA_PETABYTES: Final = "PB"
DATA_EXABYTES: Final = "EB"
DATA_ZETTABYTES: Final = "ZB"
DATA_YOTTABYTES: Final = "YB"
DATA_KIBIBYTES: Final = "KiB"
DATA_MEBIBYTES: Final = "MiB"
DATA_GIBIBYTES: Final = "GiB"
DATA_TEBIBYTES: Final = "TiB"
DATA_PEBIBYTES: Final = "PiB"
DATA_EXBIBYTES: Final = "EiB"
DATA_ZEBIBYTES: Final = "ZiB"
DATA_YOBIBYTES: Final = "YiB"
DATA_RATE_BITS_PER_SECOND: Final = "bit/s"
DATA_RATE_KILOBITS_PER_SECOND: Final = "kbit/s"
DATA_RATE_MEGABITS_PER_SECOND: Final = "Mbit/s"
DATA_RATE_GIGABITS_PER_SECOND: Final = "Gbit/s"
DATA_RATE_BYTES_PER_SECOND: Final = "B/s"
DATA_RATE_KILOBYTES_PER_SECOND: Final = "kB/s"
DATA_RATE_MEGABYTES_PER_SECOND: Final = "MB/s"
DATA_RATE_GIGABYTES_PER_SECOND: Final = "GB/s"
DATA_RATE_KIBIBYTES_PER_SECOND: Final = "KiB/s"
DATA_RATE_MEBIBYTES_PER_SECOND: Final = "MiB/s"
DATA_RATE_GIBIBYTES_PER_SECOND: Final = "GiB/s"

# #### SERVICES ####
SERVICE_HOMEASSISTANT_STOP: Final = "stop"
SERVICE_HOMEASSISTANT_RESTART: Final = "restart"

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
SERVICE_SET_COVER_POSITION: Final = "set_cover_position"
SERVICE_SET_COVER_TILT_POSITION: Final = "set_cover_tilt_position"
SERVICE_STOP_COVER: Final = "stop_cover"
SERVICE_STOP_COVER_TILT: Final = "stop_cover_tilt"
SERVICE_TOGGLE_COVER_TILT: Final = "toggle_cover_tilt"

SERVICE_SELECT_OPTION: Final = "select_option"

# #### API / REMOTE ####
SERVER_PORT: Final = 8123

URL_ROOT: Final = "/"
URL_API: Final = "/api/"
URL_API_STREAM: Final = "/api/stream"
URL_API_CONFIG: Final = "/api/config"
URL_API_DISCOVERY_INFO: Final = "/api/discovery_info"
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

HTTP_OK: Final = 200
HTTP_CREATED: Final = 201
HTTP_ACCEPTED: Final = 202
HTTP_MOVED_PERMANENTLY: Final = 301
HTTP_BAD_REQUEST: Final = 400
HTTP_UNAUTHORIZED: Final = 401
HTTP_FORBIDDEN: Final = 403
HTTP_NOT_FOUND: Final = 404
HTTP_METHOD_NOT_ALLOWED: Final = 405
HTTP_UNPROCESSABLE_ENTITY: Final = 422
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_INTERNAL_SERVER_ERROR: Final = 500
HTTP_BAD_GATEWAY: Final = 502
HTTP_SERVICE_UNAVAILABLE: Final = 503

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
MASS: Final = "mass"
PRESSURE: Final = "pressure"
VOLUME: Final = "volume"
TEMPERATURE: Final = "temperature"
SPEED_MS: Final = "speed_ms"
ILLUMINANCE: Final = "illuminance"

WEEKDAYS: Final[list[str]] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# The degree of precision for platforms
PRECISION_WHOLE: Final = 1
PRECISION_HALVES: Final = 0.5
PRECISION_TENTHS: Final = 0.1

# Static list of entities that will never be exposed to
# cloud, alexa, or google_home components
CLOUD_NEVER_EXPOSED_ENTITIES: Final[list[str]] = ["group.all_locks"]

# The ID of the Home Assistant Cast App
CAST_APP_ID_HOMEASSISTANT: Final = "B12CE3CA"
