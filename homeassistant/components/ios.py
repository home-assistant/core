"""
Native Home Assistant iOS app component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/ecosystem/ios/
"""
import asyncio
import logging
import datetime

import voluptuous as vol
# from voluptuous.humanize import humanize_error

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (HTTP_INTERNAL_SERVER_ERROR,
                                 HTTP_BAD_REQUEST)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.util.json import load_json, save_json


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'ios'

DEPENDENCIES = ['device_tracker', 'http', 'zeroconf']

CONF_PUSH = 'push'
CONF_PUSH_CATEGORIES = 'categories'
CONF_PUSH_CATEGORIES_NAME = 'name'
CONF_PUSH_CATEGORIES_IDENTIFIER = 'identifier'
CONF_PUSH_CATEGORIES_ACTIONS = 'actions'

CONF_PUSH_ACTIONS_IDENTIFIER = 'identifier'
CONF_PUSH_ACTIONS_TITLE = 'title'
CONF_PUSH_ACTIONS_ACTIVATION_MODE = 'activationMode'
CONF_PUSH_ACTIONS_AUTHENTICATION_REQUIRED = 'authenticationRequired'
CONF_PUSH_ACTIONS_DESTRUCTIVE = 'destructive'
CONF_PUSH_ACTIONS_BEHAVIOR = 'behavior'
CONF_PUSH_ACTIONS_CONTEXT = 'context'
CONF_PUSH_ACTIONS_TEXT_INPUT_BUTTON_TITLE = 'textInputButtonTitle'
CONF_PUSH_ACTIONS_TEXT_INPUT_PLACEHOLDER = 'textInputPlaceholder'

ATTR_FOREGROUND = 'foreground'
ATTR_BACKGROUND = 'background'

ACTIVATION_MODES = [ATTR_FOREGROUND, ATTR_BACKGROUND]

ATTR_DEFAULT_BEHAVIOR = 'default'
ATTR_TEXT_INPUT_BEHAVIOR = 'textInput'

BEHAVIORS = [ATTR_DEFAULT_BEHAVIOR, ATTR_TEXT_INPUT_BEHAVIOR]

ATTR_LAST_SEEN_AT = 'lastSeenAt'

ATTR_DEVICE = 'device'
ATTR_PUSH_TOKEN = 'pushToken'
ATTR_APP = 'app'
ATTR_PERMISSIONS = 'permissions'
ATTR_PUSH_ID = 'pushId'
ATTR_DEVICE_ID = 'deviceId'
ATTR_PUSH_SOUNDS = 'pushSounds'
ATTR_BATTERY = 'battery'

ATTR_DEVICE_NAME = 'name'
ATTR_DEVICE_LOCALIZED_MODEL = 'localizedModel'
ATTR_DEVICE_MODEL = 'model'
ATTR_DEVICE_PERMANENT_ID = 'permanentID'
ATTR_DEVICE_SYSTEM_VERSION = 'systemVersion'
ATTR_DEVICE_TYPE = 'type'
ATTR_DEVICE_SYSTEM_NAME = 'systemName'

ATTR_APP_BUNDLE_IDENTIFIER = 'bundleIdentifier'
ATTR_APP_BUILD_NUMBER = 'buildNumber'
ATTR_APP_VERSION_NUMBER = 'versionNumber'

ATTR_LOCATION_PERMISSION = 'location'
ATTR_NOTIFICATIONS_PERMISSION = 'notifications'

PERMISSIONS = [ATTR_LOCATION_PERMISSION, ATTR_NOTIFICATIONS_PERMISSION]

ATTR_BATTERY_STATE = 'state'
ATTR_BATTERY_LEVEL = 'level'

ATTR_BATTERY_STATE_UNPLUGGED = 'Unplugged'
ATTR_BATTERY_STATE_CHARGING = 'Charging'
ATTR_BATTERY_STATE_FULL = 'Full'
ATTR_BATTERY_STATE_UNKNOWN = 'Unknown'

BATTERY_STATES = [ATTR_BATTERY_STATE_UNPLUGGED, ATTR_BATTERY_STATE_CHARGING,
                  ATTR_BATTERY_STATE_FULL, ATTR_BATTERY_STATE_UNKNOWN]

ATTR_DEVICES = 'devices'

ACTION_SCHEMA = vol.Schema({
    vol.Required(CONF_PUSH_ACTIONS_IDENTIFIER): vol.Upper,
    vol.Required(CONF_PUSH_ACTIONS_TITLE): cv.string,
    vol.Optional(CONF_PUSH_ACTIONS_ACTIVATION_MODE,
                 default=ATTR_BACKGROUND): vol.In(ACTIVATION_MODES),
    vol.Optional(CONF_PUSH_ACTIONS_AUTHENTICATION_REQUIRED,
                 default=False): cv.boolean,
    vol.Optional(CONF_PUSH_ACTIONS_DESTRUCTIVE,
                 default=False): cv.boolean,
    vol.Optional(CONF_PUSH_ACTIONS_BEHAVIOR,
                 default=ATTR_DEFAULT_BEHAVIOR): vol.In(BEHAVIORS),
    vol.Optional(CONF_PUSH_ACTIONS_TEXT_INPUT_BUTTON_TITLE): cv.string,
    vol.Optional(CONF_PUSH_ACTIONS_TEXT_INPUT_PLACEHOLDER): cv.string,
}, extra=vol.ALLOW_EXTRA)

ACTION_SCHEMA_LIST = vol.All(cv.ensure_list, [ACTION_SCHEMA])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        CONF_PUSH: {
            CONF_PUSH_CATEGORIES: vol.All(cv.ensure_list, [{
                vol.Required(CONF_PUSH_CATEGORIES_NAME): cv.string,
                vol.Required(CONF_PUSH_CATEGORIES_IDENTIFIER): vol.Lower,
                vol.Required(CONF_PUSH_CATEGORIES_ACTIONS): ACTION_SCHEMA_LIST
            }])
        }
    }
}, extra=vol.ALLOW_EXTRA)

IDENTIFY_DEVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_NAME): cv.string,
    vol.Required(ATTR_DEVICE_LOCALIZED_MODEL): cv.string,
    vol.Required(ATTR_DEVICE_MODEL): cv.string,
    vol.Required(ATTR_DEVICE_PERMANENT_ID): cv.string,
    vol.Required(ATTR_DEVICE_SYSTEM_VERSION): cv.string,
    vol.Required(ATTR_DEVICE_TYPE): cv.string,
    vol.Required(ATTR_DEVICE_SYSTEM_NAME): cv.string,
}, extra=vol.ALLOW_EXTRA)

IDENTIFY_DEVICE_SCHEMA_CONTAINER = vol.All(dict, IDENTIFY_DEVICE_SCHEMA)

IDENTIFY_APP_SCHEMA = vol.Schema({
    vol.Required(ATTR_APP_BUNDLE_IDENTIFIER): cv.string,
    vol.Required(ATTR_APP_BUILD_NUMBER): cv.positive_int,
    vol.Optional(ATTR_APP_VERSION_NUMBER): cv.string
}, extra=vol.ALLOW_EXTRA)

IDENTIFY_APP_SCHEMA_CONTAINER = vol.All(dict, IDENTIFY_APP_SCHEMA)

IDENTIFY_BATTERY_SCHEMA = vol.Schema({
    vol.Required(ATTR_BATTERY_LEVEL): cv.positive_int,
    vol.Required(ATTR_BATTERY_STATE): vol.In(BATTERY_STATES)
}, extra=vol.ALLOW_EXTRA)

IDENTIFY_BATTERY_SCHEMA_CONTAINER = vol.All(dict, IDENTIFY_BATTERY_SCHEMA)

IDENTIFY_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE): IDENTIFY_DEVICE_SCHEMA_CONTAINER,
    vol.Required(ATTR_BATTERY): IDENTIFY_BATTERY_SCHEMA_CONTAINER,
    vol.Required(ATTR_PUSH_TOKEN): cv.string,
    vol.Required(ATTR_APP): IDENTIFY_APP_SCHEMA_CONTAINER,
    vol.Required(ATTR_PERMISSIONS): vol.All(cv.ensure_list,
                                            [vol.In(PERMISSIONS)]),
    vol.Required(ATTR_PUSH_ID): cv.string,
    vol.Required(ATTR_DEVICE_ID): cv.string,
    vol.Optional(ATTR_PUSH_SOUNDS): list
}, extra=vol.ALLOW_EXTRA)

CONFIGURATION_FILE = '.ios.conf'

CONFIG_FILE = {ATTR_DEVICES: {}}

CONFIG_FILE_PATH = ""


def devices_with_push():
    """Return a dictionary of push enabled targets."""
    targets = {}
    for device_name, device in CONFIG_FILE[ATTR_DEVICES].items():
        if device.get(ATTR_PUSH_ID) is not None:
            targets[device_name] = device.get(ATTR_PUSH_ID)
    return targets


def enabled_push_ids():
    """Return a list of push enabled target push IDs."""
    push_ids = list()
    # pylint: disable=unused-variable
    for device in CONFIG_FILE[ATTR_DEVICES].values():
        if device.get(ATTR_PUSH_ID) is not None:
            push_ids.append(device.get(ATTR_PUSH_ID))
    return push_ids


def devices():
    """Return a dictionary of all identified devices."""
    return CONFIG_FILE[ATTR_DEVICES]


def device_name_for_push_id(push_id):
    """Return the device name for the push ID."""
    for device_name, device in CONFIG_FILE[ATTR_DEVICES].items():
        if device.get(ATTR_PUSH_ID) is push_id:
            return device_name
    return None


def setup(hass, config):
    """Set up the iOS component."""
    # pylint: disable=global-statement, import-error
    global CONFIG_FILE
    global CONFIG_FILE_PATH

    CONFIG_FILE_PATH = hass.config.path(CONFIGURATION_FILE)

    CONFIG_FILE = load_json(CONFIG_FILE_PATH)

    if CONFIG_FILE == {}:
        CONFIG_FILE[ATTR_DEVICES] = {}

    discovery.load_platform(hass, 'notify', DOMAIN, {}, config)

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)

    hass.http.register_view(iOSIdentifyDeviceView)

    app_config = config.get(DOMAIN, {})
    hass.http.register_view(iOSPushConfigView(app_config.get(CONF_PUSH, {})))

    return True


# pylint: disable=invalid-name
class iOSPushConfigView(HomeAssistantView):
    """A view that provides the push categories configuration."""

    url = '/api/ios/push'
    name = 'api:ios:push'

    def __init__(self, push_config):
        """Init the view."""
        self.push_config = push_config

    @callback
    def get(self, request):
        """Handle the GET request for the push configuration."""
        return self.json(self.push_config)


class iOSIdentifyDeviceView(HomeAssistantView):
    """A view that accepts device identification requests."""

    url = '/api/ios/identify'
    name = 'api:ios:identify'

    @asyncio.coroutine
    def post(self, request):
        """Handle the POST request for device identification."""
        try:
            data = yield from request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTP_BAD_REQUEST)

        # Commented for now while iOS app is getting frequent updates
        # try:
        #     data = IDENTIFY_SCHEMA(req_data)
        # except vol.Invalid as ex:
        #     return self.json_message(humanize_error(request.json, ex),
        #                              HTTP_BAD_REQUEST)

        data[ATTR_LAST_SEEN_AT] = datetime.datetime.now().isoformat()

        name = data.get(ATTR_DEVICE_ID)

        CONFIG_FILE[ATTR_DEVICES][name] = data

        try:
            save_json(CONFIG_FILE_PATH, CONFIG_FILE)
        except HomeAssistantError:
            return self.json_message("Error saving device.",
                                     HTTP_INTERNAL_SERVER_ERROR)

        return self.json({"status": "registered"})
