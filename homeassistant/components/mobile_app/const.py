"""Constants for mobile_app."""
import voluptuous as vol

from homeassistant.components.device_tracker import SERVICE_SEE_PAYLOAD_SCHEMA
from homeassistant.const import (ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
                                 CONF_WEBHOOK_ID)
from homeassistant.helpers import config_validation as cv

DOMAIN = 'mobile_app'

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONF_CLOUDHOOK_ID = 'cloudhook_id'
CONF_CLOUDHOOK_URL = 'cloudhook_url'
CONF_SECRET = 'secret'
CONF_USER_ID = 'user_id'

ATTR_DELETED_IDS = 'deleted_ids'
ATTR_REGISTRATIONS = 'registrations'
ATTR_STORE = 'store'

ATTR_APP_DATA = 'app_data'
ATTR_APP_ID = 'app_id'
ATTR_APP_NAME = 'app_name'
ATTR_APP_VERSION = 'app_version'
ATTR_DEVICE_NAME = 'device_name'
ATTR_MANUFACTURER = 'manufacturer'
ATTR_MODEL = 'model'
ATTR_OS_VERSION = 'os_version'
ATTR_SUPPORTS_ENCRYPTION = 'supports_encryption'

ATTR_EVENT_DATA = 'event_data'
ATTR_EVENT_TYPE = 'event_type'

ATTR_TEMPLATE = 'template'
ATTR_TEMPLATE_VARIABLES = 'variables'

ATTR_WEBHOOK_DATA = 'data'
ATTR_WEBHOOK_ENCRYPTED = 'encrypted'
ATTR_WEBHOOK_ENCRYPTED_DATA = 'encrypted_data'
ATTR_WEBHOOK_TYPE = 'type'

HTTP_X_CLOUD_HOOK_ID = 'X-Cloud-Hook-ID'
HTTP_X_CLOUD_HOOK_URL = 'X-Cloud-Hook-URL'

WEBHOOK_TYPE_CALL_SERVICE = 'call_service'
WEBHOOK_TYPE_FIRE_EVENT = 'fire_event'
WEBHOOK_TYPE_RENDER_TEMPLATE = 'render_template'
WEBHOOK_TYPE_UPDATE_LOCATION = 'update_location'
WEBHOOK_TYPE_UPDATE_REGISTRATION = 'update_registration'

WEBHOOK_TYPES = [WEBHOOK_TYPE_CALL_SERVICE, WEBHOOK_TYPE_FIRE_EVENT,
                 WEBHOOK_TYPE_RENDER_TEMPLATE, WEBHOOK_TYPE_UPDATE_LOCATION,
                 WEBHOOK_TYPE_UPDATE_REGISTRATION]

REGISTER_DEVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_APP_DATA, default={}): dict,
    vol.Required(ATTR_APP_ID): cv.string,
    vol.Optional(ATTR_APP_NAME): cv.string,
    vol.Required(ATTR_APP_VERSION): cv.string,
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_MANUFACTURER): cv.string,
    vol.Required(ATTR_MODEL): cv.string,
    vol.Optional(ATTR_OS_VERSION): cv.string,
    vol.Required(ATTR_SUPPORTS_ENCRYPTION, default=False): cv.boolean,
})

UPDATE_DEVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_APP_DATA, default={}): dict,
    vol.Required(ATTR_APP_VERSION): cv.string,
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_MANUFACTURER): cv.string,
    vol.Required(ATTR_MODEL): cv.string,
    vol.Optional(ATTR_OS_VERSION): cv.string,
})

WEBHOOK_PAYLOAD_SCHEMA = vol.Schema({
    vol.Required(ATTR_WEBHOOK_TYPE): vol.In(WEBHOOK_TYPES),
    vol.Required(ATTR_WEBHOOK_DATA, default={}): dict,
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
    vol.Required(ATTR_TEMPLATE): cv.string,
    vol.Optional(ATTR_TEMPLATE_VARIABLES, default={}): dict,
})

WS_TYPE_GET_REGISTRATION = 'mobile_app/get_registration'
SCHEMA_WS_GET_REGISTRATION = {
    vol.Required('type'): WS_TYPE_GET_REGISTRATION,
    vol.Required(CONF_WEBHOOK_ID): cv.string,
}

WS_TYPE_DELETE_REGISTRATION = 'mobile_app/delete_registration'
SCHEMA_WS_DELETE_REGISTRATION = {
    vol.Required('type'): WS_TYPE_DELETE_REGISTRATION,
    vol.Required(CONF_WEBHOOK_ID): cv.string,
}

WEBHOOK_SCHEMAS = {
    WEBHOOK_TYPE_CALL_SERVICE: CALL_SERVICE_SCHEMA,
    WEBHOOK_TYPE_FIRE_EVENT: FIRE_EVENT_SCHEMA,
    WEBHOOK_TYPE_RENDER_TEMPLATE: RENDER_TEMPLATE_SCHEMA,
    WEBHOOK_TYPE_UPDATE_LOCATION: SERVICE_SEE_PAYLOAD_SCHEMA,
    WEBHOOK_TYPE_UPDATE_REGISTRATION: UPDATE_DEVICE_SCHEMA,
}
