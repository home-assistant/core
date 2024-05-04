"""Native Home Assistant iOS app component."""

import datetime
from http import HTTPStatus
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.json import save_json
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import load_json_object

from .const import (
    CONF_ACTION_BACKGROUND_COLOR,
    CONF_ACTION_ICON,
    CONF_ACTION_ICON_COLOR,
    CONF_ACTION_ICON_ICON,
    CONF_ACTION_LABEL,
    CONF_ACTION_LABEL_COLOR,
    CONF_ACTION_LABEL_TEXT,
    CONF_ACTION_NAME,
    CONF_ACTION_SHOW_IN_CARPLAY,
    CONF_ACTION_SHOW_IN_WATCH,
    CONF_ACTIONS,
    DOMAIN,
)

CONF_PUSH = "push"
CONF_PUSH_CATEGORIES = "categories"
CONF_PUSH_CATEGORIES_NAME = "name"
CONF_PUSH_CATEGORIES_IDENTIFIER = "identifier"
CONF_PUSH_CATEGORIES_ACTIONS = "actions"

CONF_PUSH_ACTIONS_IDENTIFIER = "identifier"
CONF_PUSH_ACTIONS_TITLE = "title"
CONF_PUSH_ACTIONS_ACTIVATION_MODE = "activationMode"
CONF_PUSH_ACTIONS_AUTHENTICATION_REQUIRED = "authenticationRequired"
CONF_PUSH_ACTIONS_DESTRUCTIVE = "destructive"
CONF_PUSH_ACTIONS_BEHAVIOR = "behavior"
CONF_PUSH_ACTIONS_CONTEXT = "context"
CONF_PUSH_ACTIONS_TEXT_INPUT_BUTTON_TITLE = "textInputButtonTitle"
CONF_PUSH_ACTIONS_TEXT_INPUT_PLACEHOLDER = "textInputPlaceholder"

CONF_USER = "user"

ATTR_FOREGROUND = "foreground"
ATTR_BACKGROUND = "background"

ACTIVATION_MODES = [ATTR_FOREGROUND, ATTR_BACKGROUND]

ATTR_DEFAULT_BEHAVIOR = "default"
ATTR_TEXT_INPUT_BEHAVIOR = "textInput"

BEHAVIORS = [ATTR_DEFAULT_BEHAVIOR, ATTR_TEXT_INPUT_BEHAVIOR]

ATTR_LAST_SEEN_AT = "lastSeenAt"

ATTR_DEVICE = "device"
ATTR_PUSH_TOKEN = "pushToken"
ATTR_APP = "app"
ATTR_PERMISSIONS = "permissions"
ATTR_PUSH_ID = "pushId"
ATTR_DEVICE_ID = "deviceId"
ATTR_PUSH_SOUNDS = "pushSounds"
ATTR_BATTERY = "battery"

ATTR_DEVICE_NAME = "name"
ATTR_DEVICE_LOCALIZED_MODEL = "localizedModel"
ATTR_DEVICE_MODEL = "model"
ATTR_DEVICE_PERMANENT_ID = "permanentID"
ATTR_DEVICE_SYSTEM_VERSION = "systemVersion"
ATTR_DEVICE_TYPE = "type"
ATTR_DEVICE_SYSTEM_NAME = "systemName"

ATTR_APP_BUNDLE_IDENTIFIER = "bundleIdentifier"
ATTR_APP_BUILD_NUMBER = "buildNumber"
ATTR_APP_VERSION_NUMBER = "versionNumber"

ATTR_LOCATION_PERMISSION = "location"
ATTR_NOTIFICATIONS_PERMISSION = "notifications"

PERMISSIONS = [ATTR_LOCATION_PERMISSION, ATTR_NOTIFICATIONS_PERMISSION]

ATTR_BATTERY_STATE = "state"
ATTR_BATTERY_LEVEL = "level"

ATTR_BATTERY_STATE_UNPLUGGED = "Not Charging"
ATTR_BATTERY_STATE_CHARGING = "Charging"
ATTR_BATTERY_STATE_FULL = "Full"
ATTR_BATTERY_STATE_UNKNOWN = "Unknown"

BATTERY_STATES = [
    ATTR_BATTERY_STATE_UNPLUGGED,
    ATTR_BATTERY_STATE_CHARGING,
    ATTR_BATTERY_STATE_FULL,
    ATTR_BATTERY_STATE_UNKNOWN,
]

ATTR_DEVICES = "devices"

PUSH_ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PUSH_ACTIONS_IDENTIFIER): vol.Upper,
        vol.Required(CONF_PUSH_ACTIONS_TITLE): cv.string,
        vol.Optional(
            CONF_PUSH_ACTIONS_ACTIVATION_MODE, default=ATTR_BACKGROUND
        ): vol.In(ACTIVATION_MODES),
        vol.Optional(
            CONF_PUSH_ACTIONS_AUTHENTICATION_REQUIRED, default=False
        ): cv.boolean,
        vol.Optional(CONF_PUSH_ACTIONS_DESTRUCTIVE, default=False): cv.boolean,
        vol.Optional(CONF_PUSH_ACTIONS_BEHAVIOR, default=ATTR_DEFAULT_BEHAVIOR): vol.In(
            BEHAVIORS
        ),
        vol.Optional(CONF_PUSH_ACTIONS_TEXT_INPUT_BUTTON_TITLE): cv.string,
        vol.Optional(CONF_PUSH_ACTIONS_TEXT_INPUT_PLACEHOLDER): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

PUSH_ACTION_LIST_SCHEMA = vol.All(cv.ensure_list, [PUSH_ACTION_SCHEMA])

PUSH_CATEGORY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PUSH_CATEGORIES_NAME): cv.string,
        vol.Required(CONF_PUSH_CATEGORIES_IDENTIFIER): vol.Lower,
        vol.Required(CONF_PUSH_CATEGORIES_ACTIONS): PUSH_ACTION_LIST_SCHEMA,
    }
)

PUSH_CATEGORY_LIST_SCHEMA = vol.All(cv.ensure_list, [PUSH_CATEGORY_SCHEMA])

ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACTION_NAME): cv.string,
        vol.Optional(CONF_ACTION_BACKGROUND_COLOR): cv.string,
        vol.Optional(CONF_ACTION_LABEL): {
            vol.Optional(CONF_ACTION_LABEL_TEXT): cv.string,
            vol.Optional(CONF_ACTION_LABEL_COLOR): cv.string,
        },
        vol.Optional(CONF_ACTION_ICON): {
            vol.Optional(CONF_ACTION_ICON_ICON): cv.string,
            vol.Optional(CONF_ACTION_ICON_COLOR): cv.string,
        },
        vol.Optional(CONF_ACTION_SHOW_IN_CARPLAY): cv.boolean,
        vol.Optional(CONF_ACTION_SHOW_IN_WATCH): cv.boolean,
    },
)

ACTION_LIST_SCHEMA = vol.All(cv.ensure_list, [ACTION_SCHEMA])

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_PUSH),
            {
                CONF_PUSH: {CONF_PUSH_CATEGORIES: PUSH_CATEGORY_LIST_SCHEMA},
                CONF_ACTIONS: ACTION_LIST_SCHEMA,
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)

IDENTIFY_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(ATTR_DEVICE_LOCALIZED_MODEL): cv.string,
        vol.Required(ATTR_DEVICE_MODEL): cv.string,
        vol.Required(ATTR_DEVICE_PERMANENT_ID): cv.string,
        vol.Required(ATTR_DEVICE_SYSTEM_VERSION): cv.string,
        vol.Required(ATTR_DEVICE_TYPE): cv.string,
        vol.Required(ATTR_DEVICE_SYSTEM_NAME): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

IDENTIFY_DEVICE_SCHEMA_CONTAINER = vol.All(dict, IDENTIFY_DEVICE_SCHEMA)

IDENTIFY_APP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_APP_BUNDLE_IDENTIFIER): cv.string,
        vol.Required(ATTR_APP_BUILD_NUMBER): cv.positive_int,
        vol.Optional(ATTR_APP_VERSION_NUMBER): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

IDENTIFY_APP_SCHEMA_CONTAINER = vol.All(dict, IDENTIFY_APP_SCHEMA)

IDENTIFY_BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BATTERY_LEVEL): cv.positive_int,
        vol.Required(ATTR_BATTERY_STATE): vol.In(BATTERY_STATES),
    },
    extra=vol.ALLOW_EXTRA,
)

IDENTIFY_BATTERY_SCHEMA_CONTAINER = vol.All(dict, IDENTIFY_BATTERY_SCHEMA)

IDENTIFY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE): IDENTIFY_DEVICE_SCHEMA_CONTAINER,
        vol.Required(ATTR_BATTERY): IDENTIFY_BATTERY_SCHEMA_CONTAINER,
        vol.Required(ATTR_PUSH_TOKEN): cv.string,
        vol.Required(ATTR_APP): IDENTIFY_APP_SCHEMA_CONTAINER,
        vol.Required(ATTR_PERMISSIONS): vol.All(cv.ensure_list, [vol.In(PERMISSIONS)]),
        vol.Required(ATTR_PUSH_ID): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_PUSH_SOUNDS): list,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIGURATION_FILE = ".ios.conf"

PLATFORMS = [Platform.SENSOR]


def devices_with_push(hass: HomeAssistant) -> dict[str, str]:
    """Return a dictionary of push enabled targets."""
    return {
        device_name: device.get(ATTR_PUSH_ID)
        for device_name, device in hass.data[DOMAIN][ATTR_DEVICES].items()
        if device.get(ATTR_PUSH_ID) is not None
    }


def enabled_push_ids(hass: HomeAssistant) -> list[str]:
    """Return a list of push enabled target push IDs."""
    return [
        device.get(ATTR_PUSH_ID)
        for device in hass.data[DOMAIN][ATTR_DEVICES].values()
        if device.get(ATTR_PUSH_ID) is not None
    ]


def devices(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Return a dictionary of all identified devices."""
    return hass.data[DOMAIN][ATTR_DEVICES]  # type: ignore[no-any-return]


def device_name_for_push_id(hass: HomeAssistant, push_id: str) -> str | None:
    """Return the device name for the push ID."""
    for device_name, device in hass.data[DOMAIN][ATTR_DEVICES].items():
        if device.get(ATTR_PUSH_ID) is push_id:
            return device_name  # type: ignore[no-any-return]
    return None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the iOS component."""
    conf: ConfigType | None = config.get(DOMAIN)

    ios_config = await hass.async_add_executor_job(
        load_json_object, hass.config.path(CONFIGURATION_FILE)
    )

    if ios_config == {}:
        ios_config[ATTR_DEVICES] = {}

    if CONF_PUSH not in (conf_user := conf or {}):
        conf_user[CONF_PUSH] = {}

    ios_config[CONF_USER] = conf_user

    hass.data[DOMAIN] = ios_config

    # No entry support for notify component yet
    discovery.load_platform(hass, Platform.NOTIFY, DOMAIN, {}, config)

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up an iOS entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.http.register_view(iOSIdentifyDeviceView(hass.config.path(CONFIGURATION_FILE)))
    hass.http.register_view(iOSPushConfigView(hass.data[DOMAIN][CONF_USER][CONF_PUSH]))
    hass.http.register_view(iOSConfigView(hass.data[DOMAIN][CONF_USER]))

    return True


class iOSPushConfigView(HomeAssistantView):
    """A view that provides the push categories configuration."""

    url = "/api/ios/push"
    name = "api:ios:push"

    def __init__(self, push_config: dict[str, Any]) -> None:
        """Init the view."""
        self.push_config = push_config

    @callback
    def get(self, request: web.Request) -> web.Response:
        """Handle the GET request for the push configuration."""
        return self.json(self.push_config)


class iOSConfigView(HomeAssistantView):
    """A view that provides the whole user-defined configuration."""

    url = "/api/ios/config"
    name = "api:ios:config"

    def __init__(self, config: dict[str, Any]) -> None:
        """Init the view."""
        self.config = config

    @callback
    def get(self, request: web.Request) -> web.Response:
        """Handle the GET request for the user-defined configuration."""
        return self.json(self.config)


class iOSIdentifyDeviceView(HomeAssistantView):
    """A view that accepts device identification requests."""

    url = "/api/ios/identify"
    name = "api:ios:identify"

    def __init__(self, config_path: str) -> None:
        """Initialize the view."""
        self._config_path = config_path

    async def post(self, request: web.Request) -> web.Response:
        """Handle the POST request for device identification."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)

        hass = request.app[KEY_HASS]

        data[ATTR_LAST_SEEN_AT] = datetime.datetime.now().isoformat()

        device_id = data[ATTR_DEVICE_ID]

        hass.data[DOMAIN][ATTR_DEVICES][device_id] = data

        async_dispatcher_send(hass, f"{DOMAIN}.{device_id}", data)

        try:
            save_json(self._config_path, hass.data[DOMAIN])
        except HomeAssistantError:
            return self.json_message(
                "Error saving device.", HTTPStatus.INTERNAL_SERVER_ERROR
            )

        return self.json({"status": "registered"})
