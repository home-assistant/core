"""Constants for Google Assistant."""
DOMAIN = 'google_assistant'

GOOGLE_ASSISTANT_API_ENDPOINT = '/api/google_assistant'

ATTR_GOOGLE_ASSISTANT = 'google_assistant'
ATTR_GOOGLE_ASSISTANT_NAME = 'google_assistant_name'

CONF_EXPOSE_BY_DEFAULT = 'expose_by_default'
CONF_EXPOSED_DOMAINS = 'exposed_domains'
CONF_PROJECT_ID = 'project_id'
CONF_ACCESS_TOKEN = 'access_token'
CONF_CLIENT_ID = 'client_id'
CONF_ALIASES = 'aliases'

DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    'switch', 'light', 'group', 'media_player', 'fan', 'cover'
]

PREFIX_TRAITS = 'action.devices.traits.'
TRAIT_ONOFF = PREFIX_TRAITS + 'OnOff'
TRAIT_BRIGHTNESS = PREFIX_TRAITS + 'Brightness'
TRAIT_RGB_COLOR = PREFIX_TRAITS + 'ColorSpectrum'
TRAIT_COLOR_TEMP = PREFIX_TRAITS + 'ColorTemperature'
TRAIT_SCENE = PREFIX_TRAITS + 'Scene'

PREFIX_COMMANDS = 'action.devices.commands.'
COMMAND_ONOFF = PREFIX_COMMANDS + 'OnOff'
COMMAND_BRIGHTNESS = PREFIX_COMMANDS + 'BrightnessAbsolute'
COMMAND_COLOR = PREFIX_COMMANDS + 'ColorAbsolute'
COMMAND_ACTIVATESCENE = PREFIX_COMMANDS + 'ActivateScene'

PREFIX_TYPES = 'action.devices.types.'
TYPE_LIGHT = PREFIX_TYPES + 'LIGHT'
TYPE_SWITCH = PREFIX_TYPES + 'SWITCH'
TYPE_SCENE = PREFIX_TYPES + 'SCENE'
