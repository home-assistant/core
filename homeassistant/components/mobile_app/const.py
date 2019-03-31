"""Constants for mobile_app."""
import voluptuous as vol

from homeassistant.components.binary_sensor import (DEVICE_CLASSES as
                                                    BINARY_SENSOR_CLASSES)
from homeassistant.components.sensor import DEVICE_CLASSES as SENSOR_CLASSES
from homeassistant.components.device_tracker import (ATTR_BATTERY,
                                                     ATTR_GPS,
                                                     ATTR_GPS_ACCURACY,
                                                     ATTR_LOCATION_NAME)
from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA)
from homeassistant.helpers import config_validation as cv

DOMAIN = 'mobile_app'

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONF_CLOUDHOOK_URL = 'cloudhook_url'
CONF_REMOTE_UI_URL = 'remote_ui_url'
CONF_SECRET = 'secret'
CONF_USER_ID = 'user_id'

DATA_BINARY_SENSOR = 'binary_sensor'
DATA_CONFIG_ENTRIES = 'config_entries'
DATA_DELETED_IDS = 'deleted_ids'
DATA_DEVICES = 'devices'
DATA_SENSOR = 'sensor'
DATA_STORE = 'store'

ATTR_APP_COMPONENT = 'app_component'
ATTR_APP_DATA = 'app_data'
ATTR_APP_ID = 'app_id'
ATTR_APP_NAME = 'app_name'
ATTR_APP_VERSION = 'app_version'
ATTR_CONFIG_ENTRY_ID = 'entry_id'
ATTR_DEVICE_ID = 'device_id'
ATTR_DEVICE_NAME = 'device_name'
ATTR_MANUFACTURER = 'manufacturer'
ATTR_MODEL = 'model'
ATTR_OS_NAME = 'os_name'
ATTR_OS_VERSION = 'os_version'
ATTR_SUPPORTS_ENCRYPTION = 'supports_encryption'

ATTR_EVENT_DATA = 'event_data'
ATTR_EVENT_TYPE = 'event_type'

ATTR_TEMPLATE = 'template'
ATTR_TEMPLATE_VARIABLES = 'variables'

ATTR_SPEED = 'speed'
ATTR_ALTITUDE = 'altitude'
ATTR_COURSE = 'course'
ATTR_VERTICAL_ACCURACY = 'vertical_accuracy'

ATTR_WEBHOOK_DATA = 'data'
ATTR_WEBHOOK_ENCRYPTED = 'encrypted'
ATTR_WEBHOOK_ENCRYPTED_DATA = 'encrypted_data'
ATTR_WEBHOOK_TYPE = 'type'

ERR_ENCRYPTION_REQUIRED = 'encryption_required'
ERR_INVALID_COMPONENT = 'invalid_component'
ERR_SENSOR_NOT_REGISTERED = 'not_registered'
ERR_SENSOR_DUPLICATE_UNIQUE_ID = 'duplicate_unique_id'

WEBHOOK_TYPE_CALL_SERVICE = 'call_service'
WEBHOOK_TYPE_FIRE_EVENT = 'fire_event'
WEBHOOK_TYPE_REGISTER_SENSOR = 'register_sensor'
WEBHOOK_TYPE_RENDER_TEMPLATE = 'render_template'
WEBHOOK_TYPE_UPDATE_LOCATION = 'update_location'
WEBHOOK_TYPE_UPDATE_REGISTRATION = 'update_registration'
WEBHOOK_TYPE_UPDATE_SENSOR_STATES = 'update_sensor_states'

WEBHOOK_TYPES = [WEBHOOK_TYPE_CALL_SERVICE, WEBHOOK_TYPE_FIRE_EVENT,
                 WEBHOOK_TYPE_REGISTER_SENSOR, WEBHOOK_TYPE_RENDER_TEMPLATE,
                 WEBHOOK_TYPE_UPDATE_LOCATION,
                 WEBHOOK_TYPE_UPDATE_REGISTRATION,
                 WEBHOOK_TYPE_UPDATE_SENSOR_STATES]


REGISTRATION_SCHEMA = vol.Schema({
    vol.Optional(ATTR_APP_COMPONENT): cv.string,
    vol.Optional(ATTR_APP_DATA, default={}): dict,
    vol.Required(ATTR_APP_ID): cv.string,
    vol.Required(ATTR_APP_NAME): cv.string,
    vol.Required(ATTR_APP_VERSION): cv.string,
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_MANUFACTURER): cv.string,
    vol.Required(ATTR_MODEL): cv.string,
    vol.Required(ATTR_OS_NAME): cv.string,
    vol.Optional(ATTR_OS_VERSION): cv.string,
    vol.Required(ATTR_SUPPORTS_ENCRYPTION, default=False): cv.boolean,
})

UPDATE_REGISTRATION_SCHEMA = vol.Schema({
    vol.Optional(ATTR_APP_DATA, default={}): dict,
    vol.Required(ATTR_APP_VERSION): cv.string,
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_MANUFACTURER): cv.string,
    vol.Required(ATTR_MODEL): cv.string,
    vol.Optional(ATTR_OS_VERSION): cv.string,
})

WEBHOOK_PAYLOAD_SCHEMA = vol.Schema({
    vol.Required(ATTR_WEBHOOK_TYPE): cv.string,  # vol.In(WEBHOOK_TYPES)
    vol.Required(ATTR_WEBHOOK_DATA, default={}): vol.Any(dict, list),
    vol.Optional(ATTR_WEBHOOK_ENCRYPTED, default=False): cv.boolean,
    vol.Optional(ATTR_WEBHOOK_ENCRYPTED_DATA): cv.string,
})

CALL_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_DOMAIN): cv.string,
    vol.Required(ATTR_SERVICE): cv.string,
    vol.Optional(ATTR_SERVICE_DATA, default={}): dict,
})

FIRE_EVENT_SCHEMA = vol.Schema({
    vol.Required(ATTR_EVENT_TYPE): cv.string,
    vol.Optional(ATTR_EVENT_DATA, default={}): dict,
})

RENDER_TEMPLATE_SCHEMA = vol.Schema({
    str: {
        vol.Required(ATTR_TEMPLATE): cv.template,
        vol.Optional(ATTR_TEMPLATE_VARIABLES, default={}): dict,
    }
})

UPDATE_LOCATION_SCHEMA = vol.Schema({
    vol.Optional(ATTR_LOCATION_NAME): cv.string,
    vol.Required(ATTR_GPS): cv.gps,
    vol.Required(ATTR_GPS_ACCURACY): cv.positive_int,
    vol.Optional(ATTR_BATTERY): cv.positive_int,
    vol.Optional(ATTR_SPEED): cv.positive_int,
    vol.Optional(ATTR_ALTITUDE): cv.positive_int,
    vol.Optional(ATTR_COURSE): cv.positive_int,
    vol.Optional(ATTR_VERTICAL_ACCURACY): cv.positive_int,
})

ATTR_SENSOR_ATTRIBUTES = 'attributes'
ATTR_SENSOR_DEVICE_CLASS = 'device_class'
ATTR_SENSOR_ICON = 'icon'
ATTR_SENSOR_NAME = 'name'
ATTR_SENSOR_STATE = 'state'
ATTR_SENSOR_TYPE = 'type'
ATTR_SENSOR_TYPE_BINARY_SENSOR = 'binary_sensor'
ATTR_SENSOR_TYPE_SENSOR = 'sensor'
ATTR_SENSOR_UNIQUE_ID = 'unique_id'
ATTR_SENSOR_UOM = 'unit_of_measurement'

SENSOR_TYPES = [ATTR_SENSOR_TYPE_BINARY_SENSOR, ATTR_SENSOR_TYPE_SENSOR]

COMBINED_CLASSES = sorted(set(BINARY_SENSOR_CLASSES + SENSOR_CLASSES))

SIGNAL_SENSOR_UPDATE = DOMAIN + '_sensor_update'

REGISTER_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(ATTR_SENSOR_ATTRIBUTES, default={}): dict,
    vol.Optional(ATTR_SENSOR_DEVICE_CLASS): vol.All(vol.Lower,
                                                    vol.In(COMBINED_CLASSES)),
    vol.Required(ATTR_SENSOR_NAME): cv.string,
    vol.Required(ATTR_SENSOR_TYPE): vol.In(SENSOR_TYPES),
    vol.Required(ATTR_SENSOR_UNIQUE_ID): cv.string,
    vol.Required(ATTR_SENSOR_UOM): cv.string,
    vol.Required(ATTR_SENSOR_STATE): vol.Any(bool, str, int, float),
    vol.Optional(ATTR_SENSOR_ICON, default='mdi:cellphone'): cv.icon,
})

UPDATE_SENSOR_STATE_SCHEMA = vol.All(cv.ensure_list, [vol.Schema({
    vol.Optional(ATTR_SENSOR_ATTRIBUTES, default={}): dict,
    vol.Optional(ATTR_SENSOR_ICON, default='mdi:cellphone'): cv.icon,
    vol.Required(ATTR_SENSOR_STATE): vol.Any(bool, str, int, float),
    vol.Required(ATTR_SENSOR_TYPE): vol.In(SENSOR_TYPES),
    vol.Required(ATTR_SENSOR_UNIQUE_ID): cv.string,
})])

WEBHOOK_SCHEMAS = {
    WEBHOOK_TYPE_CALL_SERVICE: CALL_SERVICE_SCHEMA,
    WEBHOOK_TYPE_FIRE_EVENT: FIRE_EVENT_SCHEMA,
    WEBHOOK_TYPE_REGISTER_SENSOR: REGISTER_SENSOR_SCHEMA,
    WEBHOOK_TYPE_RENDER_TEMPLATE: RENDER_TEMPLATE_SCHEMA,
    WEBHOOK_TYPE_UPDATE_LOCATION: UPDATE_LOCATION_SCHEMA,
    WEBHOOK_TYPE_UPDATE_REGISTRATION: UPDATE_REGISTRATION_SCHEMA,
    WEBHOOK_TYPE_UPDATE_SENSOR_STATES: UPDATE_SENSOR_STATE_SCHEMA,
}
