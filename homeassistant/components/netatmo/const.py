"""Constants used by the Netatmo component."""
API = "api"

DOMAIN = "netatmo"
MANUFACTURER = "Netatmo"

MODELS = {
    "NAPlug": "Relay",
    "NATherm1": "Smart Thermostat",
    "NRV": "Smart Radiator Valves",
    "NACamera": "Smart Indoor Camera",
    "NOC": "Smart Outdoor Camera",
    "NSD": "Smart Smoke Alarm",
    "NACamDoorTag": "Smart Door and Window Sensors",
    "NHC": "Smart Indoor Air Quality Monitor",
    "NAMain": "Smart Home Weather station – indoor module",
    "NAModule1": "Smart Home Weather station – outdoor module",
    "NAModule4": "Smart Additional Indoor module",
    "NAModule3": "Smart Rain Gauge",
    "NAModule2": "Smart Anemometer",
    "public": "Public Weather stations",
}

AUTH = "netatmo_auth"
CONF_PUBLIC = "public_sensor_config"
CAMERA_DATA = "netatmo_camera"
HOME_DATA = "netatmo_home_data"
DATA_HANDLER = "netatmo_data_handler"
SIGNAL_NAME = "signal_name"

CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_WEATHER_AREAS = "weather_areas"
CONF_NEW_AREA = "new_area"
CONF_AREA_NAME = "area_name"
CONF_LAT_NE = "lat_ne"
CONF_LON_NE = "lon_ne"
CONF_LAT_SW = "lat_sw"
CONF_LON_SW = "lon_sw"
CONF_PUBLIC_MODE = "mode"
CONF_UUID = "uuid"

OAUTH2_AUTHORIZE = "https://api.netatmo.com/oauth2/authorize"
OAUTH2_TOKEN = "https://api.netatmo.com/oauth2/token"

DATA_DEVICE_IDS = "netatmo_device_ids"
DATA_HOMES = "netatmo_homes"
DATA_PERSONS = "netatmo_persons"
DATA_SCHEDULES = "netatmo_schedules"

NETATMO_WEBHOOK_URL = None
NETATMO_EVENT = "netatmo_event"

DEFAULT_PERSON = "Unknown"
DEFAULT_DISCOVERY = True
DEFAULT_WEBHOOKS = False

ATTR_ID = "id"
ATTR_PSEUDO = "pseudo"
ATTR_NAME = "name"
ATTR_EVENT_TYPE = "event_type"
ATTR_HEATING_POWER_REQUEST = "heating_power_request"
ATTR_HOME_ID = "home_id"
ATTR_HOME_NAME = "home_name"
ATTR_PERSON = "person"
ATTR_PERSONS = "persons"
ATTR_IS_KNOWN = "is_known"
ATTR_FACE_URL = "face_url"
ATTR_SCHEDULE_ID = "schedule_id"
ATTR_SCHEDULE_NAME = "schedule_name"
ATTR_CAMERA_LIGHT_MODE = "camera_light_mode"

SERVICE_SET_CAMERA_LIGHT = "set_camera_light"
SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_SET_PERSONS_HOME = "set_persons_home"
SERVICE_SET_PERSON_AWAY = "set_person_away"

EVENT_TYPE_CANCEL_SET_POINT = "cancel_set_point"
EVENT_TYPE_LIGHT_MODE = "light_mode"
EVENT_TYPE_OFF = "off"
EVENT_TYPE_ON = "on"
EVENT_TYPE_SET_POINT = "set_point"
EVENT_TYPE_THERM_MODE = "therm_mode"

MODE_LIGHT_ON = "on"
MODE_LIGHT_OFF = "off"
MODE_LIGHT_AUTO = "auto"
CAMERA_LIGHT_MODES = [MODE_LIGHT_ON, MODE_LIGHT_OFF, MODE_LIGHT_AUTO]
