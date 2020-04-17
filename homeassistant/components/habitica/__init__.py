"""Support for Habitica devices."""
from collections import namedtuple
import logging

from habitipy.aio import HabitipyAsync
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_PATH,
    CONF_SENSORS,
    CONF_URL,
)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

CONF_API_USER = "api_user"

DEFAULT_URL = "https://habitica.com"
DOMAIN = "habitica"

ST = SensorType = namedtuple("SensorType", ["name", "icon", "unit", "path"])

SENSORS_TYPES = {
    "name": ST("Name", None, "", ["profile", "name"]),
    "hp": ST("HP", "mdi:heart", "HP", ["stats", "hp"]),
    "maxHealth": ST("max HP", "mdi:heart", "HP", ["stats", "maxHealth"]),
    "mp": ST("Mana", "mdi:auto-fix", "MP", ["stats", "mp"]),
    "maxMP": ST("max Mana", "mdi:auto-fix", "MP", ["stats", "maxMP"]),
    "exp": ST("EXP", "mdi:star", "EXP", ["stats", "exp"]),
    "toNextLevel": ST("Next Lvl", "mdi:star", "EXP", ["stats", "toNextLevel"]),
    "lvl": ST("Lvl", "mdi:arrow-up-bold-circle-outline", "Lvl", ["stats", "lvl"]),
    "gp": ST("Gold", "mdi:coin", "Gold", ["stats", "gp"]),
    "class": ST("Class", "mdi:sword", "", ["stats", "class"]),
}

INSTANCE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_URL, default=DEFAULT_URL): cv.url,
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_API_USER): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_SENSORS, default=list(SENSORS_TYPES)): vol.All(
            cv.ensure_list, vol.Unique(), [vol.In(list(SENSORS_TYPES))]
        ),
    }
)

has_unique_values = vol.Schema(vol.Unique())  # pylint: disable=invalid-name
# because we want a handy alias


def has_all_unique_users(value):
    """Validate that all API users are unique."""
    api_users = [user[CONF_API_USER] for user in value]
    has_unique_values(api_users)
    return value


def has_all_unique_users_names(value):
    """Validate that all user's names are unique and set if any is set."""
    names = [user.get(CONF_NAME) for user in value]
    if None in names and any(name is not None for name in names):
        raise vol.Invalid("user names of all users must be set if any is set")
    if not all(name is None for name in names):
        has_unique_values(names)
    return value


INSTANCE_LIST_SCHEMA = vol.All(
    cv.ensure_list, has_all_unique_users, has_all_unique_users_names, [INSTANCE_SCHEMA]
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: INSTANCE_LIST_SCHEMA}, extra=vol.ALLOW_EXTRA)

SERVICE_API_CALL = "api_call"
ATTR_NAME = CONF_NAME
ATTR_PATH = CONF_PATH
ATTR_ARGS = "args"
EVENT_API_CALL_SUCCESS = f"{DOMAIN}_{SERVICE_API_CALL}_success"

SERVICE_API_CALL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): str,
        vol.Required(ATTR_PATH): vol.All(cv.ensure_list, [str]),
        vol.Optional(ATTR_ARGS): dict,
    }
)


async def async_setup(hass, config):
    """Set up the Habitica service."""

    conf = config[DOMAIN]
    data = hass.data[DOMAIN] = {}
    websession = async_get_clientsession(hass)

    class HAHabitipyAsync(HabitipyAsync):
        """Closure API class to hold session."""

        def __call__(self, **kwargs):
            return super().__call__(websession, **kwargs)

    for instance in conf:
        url = instance[CONF_URL]
        username = instance[CONF_API_USER]
        password = instance[CONF_API_KEY]
        name = instance.get(CONF_NAME)
        config_dict = {"url": url, "login": username, "password": password}
        api = HAHabitipyAsync(config_dict)
        user = await api.user.get()
        if name is None:
            name = user["profile"]["name"]
        data[name] = api
        if CONF_SENSORS in instance:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    "sensor",
                    DOMAIN,
                    {"name": name, "sensors": instance[CONF_SENSORS]},
                    config,
                )
            )

    async def handle_api_call(call):
        name = call.data[ATTR_NAME]
        path = call.data[ATTR_PATH]
        api = hass.data[DOMAIN].get(name)
        if api is None:
            _LOGGER.error("API_CALL: User '%s' not configured", name)
            return
        try:
            for element in path:
                api = api[element]
        except KeyError:
            _LOGGER.error(
                "API_CALL: Path %s is invalid for API on '{%s}' element", path, element
            )
            return
        kwargs = call.data.get(ATTR_ARGS, {})
        data = await api(**kwargs)
        hass.bus.async_fire(
            EVENT_API_CALL_SUCCESS, {"name": name, "path": path, "data": data}
        )

    hass.services.async_register(
        DOMAIN, SERVICE_API_CALL, handle_api_call, schema=SERVICE_API_CALL_SCHEMA
    )
    return True
