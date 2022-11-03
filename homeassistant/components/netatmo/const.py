"""Constants used by the Netatmo component."""
from homeassistant.const import Platform

API = "api"

DOMAIN = "netatmo"
MANUFACTURER = "Netatmo"
DEFAULT_ATTRIBUTION = f"Data provided by {MANUFACTURER}"

PLATFORMS = [
    Platform.CAMERA,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_URL_SECURITY = "https://home.netatmo.com/security"
CONF_URL_ENERGY = "https://my.netatmo.com/app/energy"
CONF_URL_WEATHER = "https://my.netatmo.com/app/weather"
CONF_URL_CONTROL = "https://home.netatmo.com/control"
CONF_URL_PUBLIC_WEATHER = "https://weathermap.netatmo.com/"

AUTH = "netatmo_auth"
CONF_PUBLIC = "public_sensor_config"
CAMERA_DATA = "netatmo_camera"
HOME_DATA = "netatmo_home_data"
DATA_HANDLER = "netatmo_data_handler"
SIGNAL_NAME = "signal_name"

NETATMO_CREATE_BATTERY = "netatmo_create_battery"
NETATMO_CREATE_CAMERA = "netatmo_create_camera"
NETATMO_CREATE_CAMERA_LIGHT = "netatmo_create_camera_light"
NETATMO_CREATE_CLIMATE = "netatmo_create_climate"
NETATMO_CREATE_COVER = "netatmo_create_cover"
NETATMO_CREATE_LIGHT = "netatmo_create_light"
NETATMO_CREATE_ROOM_SENSOR = "netatmo_create_room_sensor"
NETATMO_CREATE_SELECT = "netatmo_create_select"
NETATMO_CREATE_SENSOR = "netatmo_create_sensor"
NETATMO_CREATE_SWITCH = "netatmo_create_switch"
NETATMO_CREATE_WEATHER_SENSOR = "netatmo_create_weather_sensor"

CONF_AREA_NAME = "area_name"
CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_LAT_NE = "lat_ne"
CONF_LAT_SW = "lat_sw"
CONF_LON_NE = "lon_ne"
CONF_LON_SW = "lon_sw"
CONF_NEW_AREA = "new_area"
CONF_PUBLIC_MODE = "mode"
CONF_UUID = "uuid"
CONF_WEATHER_AREAS = "weather_areas"

OAUTH2_AUTHORIZE = "https://api.netatmo.com/oauth2/authorize"
OAUTH2_TOKEN = "https://api.netatmo.com/oauth2/token"

DATA_CAMERAS = "cameras"
DATA_DEVICE_IDS = "netatmo_device_ids"
DATA_EVENTS = "netatmo_events"
DATA_HOMES = "netatmo_homes"
DATA_PERSONS = "netatmo_persons"
DATA_SCHEDULES = "netatmo_schedules"

NETATMO_EVENT = "netatmo_event"
NETATMO_WEBHOOK_URL = None

DEFAULT_DISCOVERY = True
DEFAULT_PERSON = "unknown"
DEFAULT_WEBHOOKS = False

ATTR_CAMERA_LIGHT_MODE = "camera_light_mode"
ATTR_EVENT_TYPE = "event_type"
ATTR_FACE_URL = "face_url"
ATTR_HEATING_POWER_REQUEST = "heating_power_request"
ATTR_HOME_ID = "home_id"
ATTR_HOME_NAME = "home_name"
ATTR_IS_KNOWN = "is_known"
ATTR_PERSON = "person"
ATTR_PERSONS = "persons"
ATTR_PSEUDO = "pseudo"
ATTR_SCHEDULE_ID = "schedule_id"
ATTR_SCHEDULE_NAME = "schedule_name"
ATTR_SELECTED_SCHEDULE = "selected_schedule"

SERVICE_SET_CAMERA_LIGHT = "set_camera_light"
SERVICE_SET_PERSON_AWAY = "set_person_away"
SERVICE_SET_PERSONS_HOME = "set_persons_home"
SERVICE_SET_SCHEDULE = "set_schedule"

# Climate events
EVENT_TYPE_CANCEL_SET_POINT = "cancel_set_point"
EVENT_TYPE_SCHEDULE = "schedule"
EVENT_TYPE_SET_POINT = "set_point"
EVENT_TYPE_THERM_MODE = "therm_mode"
# Camera events
EVENT_TYPE_CAMERA_ANIMAL = "animal"
EVENT_TYPE_CAMERA_HUMAN = "human"
EVENT_TYPE_CAMERA_MOVEMENT = "movement"
EVENT_TYPE_CAMERA_OUTDOOR = "outdoor"
EVENT_TYPE_CAMERA_PERSON = "person"
EVENT_TYPE_CAMERA_PERSON_AWAY = "person_away"
EVENT_TYPE_CAMERA_VEHICLE = "vehicle"
EVENT_TYPE_LIGHT_MODE = "light_mode"
# Door tags
EVENT_TYPE_ALARM_STARTED = "alarm_started"
EVENT_TYPE_DOOR_TAG_BIG_MOVE = "tag_big_move"
EVENT_TYPE_DOOR_TAG_OPEN = "tag_open"
EVENT_TYPE_DOOR_TAG_SMALL_MOVE = "tag_small_move"
EVENT_TYPE_OFF = "off"
EVENT_TYPE_ON = "on"

OUTDOOR_CAMERA_TRIGGERS = [
    EVENT_TYPE_CAMERA_ANIMAL,
    EVENT_TYPE_CAMERA_HUMAN,
    EVENT_TYPE_CAMERA_OUTDOOR,
    EVENT_TYPE_CAMERA_VEHICLE,
]
INDOOR_CAMERA_TRIGGERS = [
    EVENT_TYPE_ALARM_STARTED,
    EVENT_TYPE_CAMERA_MOVEMENT,
    EVENT_TYPE_CAMERA_PERSON_AWAY,
    EVENT_TYPE_CAMERA_PERSON,
]
DOOR_TAG_TRIGGERS = [
    EVENT_TYPE_DOOR_TAG_BIG_MOVE,
    EVENT_TYPE_DOOR_TAG_OPEN,
    EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
]
CLIMATE_TRIGGERS = [
    EVENT_TYPE_CANCEL_SET_POINT,
    EVENT_TYPE_SET_POINT,
    EVENT_TYPE_THERM_MODE,
]
EVENT_ID_MAP = {
    EVENT_TYPE_ALARM_STARTED: "device_id",
    EVENT_TYPE_CAMERA_ANIMAL: "device_id",
    EVENT_TYPE_CAMERA_HUMAN: "device_id",
    EVENT_TYPE_CAMERA_MOVEMENT: "device_id",
    EVENT_TYPE_CAMERA_OUTDOOR: "device_id",
    EVENT_TYPE_CAMERA_PERSON_AWAY: "device_id",
    EVENT_TYPE_CAMERA_PERSON: "device_id",
    EVENT_TYPE_CAMERA_VEHICLE: "device_id",
    EVENT_TYPE_CANCEL_SET_POINT: "room_id",
    EVENT_TYPE_DOOR_TAG_BIG_MOVE: "device_id",
    EVENT_TYPE_DOOR_TAG_OPEN: "device_id",
    EVENT_TYPE_DOOR_TAG_SMALL_MOVE: "device_id",
    EVENT_TYPE_LIGHT_MODE: "device_id",
    EVENT_TYPE_SET_POINT: "room_id",
    EVENT_TYPE_THERM_MODE: "home_id",
}

MODE_LIGHT_AUTO = "auto"
MODE_LIGHT_OFF = "off"
MODE_LIGHT_ON = "on"
CAMERA_LIGHT_MODES = [MODE_LIGHT_ON, MODE_LIGHT_OFF, MODE_LIGHT_AUTO]

WEBHOOK_ACTIVATION = "webhook_activation"
WEBHOOK_DEACTIVATION = "webhook_deactivation"
WEBHOOK_LIGHT_MODE = "NOC-light_mode"
WEBHOOK_NACAMERA_CONNECTION = "NACamera-connection"
WEBHOOK_PUSH_TYPE = "push_type"
