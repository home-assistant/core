"""Constants for Google Assistant."""
DOMAIN = 'google_assistant'

GOOGLE_ASSISTANT_API_ENDPOINT = '/api/google_assistant'

CONF_EXPOSE = 'expose'
CONF_ENTITY_CONFIG = 'entity_config'
CONF_EXPOSE_BY_DEFAULT = 'expose_by_default'
CONF_EXPOSED_DOMAINS = 'exposed_domains'
CONF_PROJECT_ID = 'project_id'
CONF_ACCESS_TOKEN = 'access_token'
CONF_CLIENT_ID = 'client_id'
CONF_ALIASES = 'aliases'
CONF_AGENT_USER_ID = 'agent_user_id'
CONF_API_KEY = 'api_key'
CONF_ROOM_HINT = 'room'

DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    'switch', 'light', 'group', 'media_player', 'fan', 'cover', 'climate'
]
CLIMATE_MODE_HEATCOOL = 'heatcool'
CLIMATE_SUPPORTED_MODES = {'heat', 'cool', 'off', 'on', CLIMATE_MODE_HEATCOOL}

PREFIX_TYPES = 'action.devices.types.'
TYPE_LIGHT = PREFIX_TYPES + 'LIGHT'
TYPE_SWITCH = PREFIX_TYPES + 'SWITCH'
TYPE_SCENE = PREFIX_TYPES + 'SCENE'
TYPE_THERMOSTAT = PREFIX_TYPES + 'THERMOSTAT'

SERVICE_REQUEST_SYNC = 'request_sync'
HOMEGRAPH_URL = 'https://homegraph.googleapis.com/'
REQUEST_SYNC_BASE_URL = HOMEGRAPH_URL + 'v1/devices:requestSync'

# Error codes used for SmartHomeError class
# https://developers.google.com/actions/smarthome/create-app#error_responses
ERR_DEVICE_OFFLINE = "deviceOffline"
ERR_DEVICE_NOT_FOUND = "deviceNotFound"
ERR_VALUE_OUT_OF_RANGE = "valueOutOfRange"
ERR_NOT_SUPPORTED = "notSupported"
ERR_PROTOCOL_ERROR = 'protocolError'
ERR_UNKNOWN_ERROR = 'unknownError'
