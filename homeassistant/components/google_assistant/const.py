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

DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    'switch', 'light', 'group', 'media_player', 'fan', 'cover', 'climate'
]
CLIMATE_MODE_HEATCOOL = 'heatcool'
CLIMATE_SUPPORTED_MODES = {'heat', 'cool', 'off', 'on', CLIMATE_MODE_HEATCOOL}

PREFIX_TRAITS = 'action.devices.traits.'
TRAIT_ONOFF = PREFIX_TRAITS + 'OnOff'
TRAIT_BRIGHTNESS = PREFIX_TRAITS + 'Brightness'
TRAIT_RGB_COLOR = PREFIX_TRAITS + 'ColorSpectrum'
TRAIT_COLOR_TEMP = PREFIX_TRAITS + 'ColorTemperature'
TRAIT_SCENE = PREFIX_TRAITS + 'Scene'
TRAIT_TEMPERATURE_SETTING = PREFIX_TRAITS + 'TemperatureSetting'

PREFIX_COMMANDS = 'action.devices.commands.'
COMMAND_ONOFF = PREFIX_COMMANDS + 'OnOff'
COMMAND_BRIGHTNESS = PREFIX_COMMANDS + 'BrightnessAbsolute'
COMMAND_COLOR = PREFIX_COMMANDS + 'ColorAbsolute'
COMMAND_ACTIVATESCENE = PREFIX_COMMANDS + 'ActivateScene'
COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT = (
    PREFIX_COMMANDS + 'ThermostatTemperatureSetpoint')
COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE = (
    PREFIX_COMMANDS + 'ThermostatTemperatureSetRange')
COMMAND_THERMOSTAT_SET_MODE = PREFIX_COMMANDS + 'ThermostatSetMode'

PREFIX_TYPES = 'action.devices.types.'
TYPE_LIGHT = PREFIX_TYPES + 'LIGHT'
TYPE_SWITCH = PREFIX_TYPES + 'SWITCH'
TYPE_SCENE = PREFIX_TYPES + 'SCENE'
TYPE_THERMOSTAT = PREFIX_TYPES + 'THERMOSTAT'

SERVICE_REQUEST_SYNC = 'request_sync'
HOMEGRAPH_URL = 'https://homegraph.googleapis.com/'
REQUEST_SYNC_BASE_URL = HOMEGRAPH_URL + 'v1/devices:requestSync'
