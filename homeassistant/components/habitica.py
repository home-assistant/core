"""
The Habitica API component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/habitica/
"""

import logging
from collections import namedtuple

import voluptuous as vol
from homeassistant.const import \
    CONF_NAME, CONF_URL, CONF_SENSORS, CONF_PATH
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import \
    config_validation as cv, discovery

REQUIREMENTS = ['habitipy==0.2.0']
_LOGGER = logging.getLogger(__name__)
DOMAIN = "habitica"

CONF_API_USER = "api_user"
CONF_API_KEY = "api_key"

CONF_EXCLUDE_NAMES = 'exclude_names'
CONF_SENSORS_LIST = 'sensors_customization'
ST = SensorType = namedtuple('SensorType', [
    "name", "icon", "unit", "path"
])

SENSORS_TYPES = {
    'name': ST('Name', None, '', ["profile", "name"]),
    'hp': ST('HP', 'mdi:heart', 'HP', ["stats", "hp"]),
    'maxHealth': ST('max HP', 'mdi:heart', 'HP', ["stats", "maxHealth"]),
    'mp': ST('Mana', 'mdi:auto-fix', 'MP', ["stats", "mp"]),
    'maxMP': ST('max Mana', 'mdi:auto-fix', 'MP', ["stats", "maxMP"]),
    'exp': ST('EXP', 'mdi:star', 'EXP', ["stats", "exp"]),
    'toNextLevel': ST(
        'Next Lvl', 'mdi:star', 'EXP', ["stats", "toNextLevel"]),
    'lvl': ST(
        'Lvl', 'mdi:arrow-up-bold-circle-outline', 'Lvl', ["stats", "lvl"]),
    'gp': ST('Gold', 'mdi:coin', 'Gold', ["stats", "gp"]),
    'class': ST('Class', 'mdi:sword', '', ["stats", "class"])
}
ALL_SENSORS_TYPES = list(SENSORS_TYPES.keys())

INSTANCE_SCHEMA = vol.Schema({
    vol.Optional(CONF_URL): cv.url,
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_API_USER): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_SENSORS):
        vol.All(cv.ensure_list, [vol.In(ALL_SENSORS_TYPES)])
})


INSTANCE_LIST_SCHEMA = vol.All(cv.ensure_list, [INSTANCE_SCHEMA])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: INSTANCE_LIST_SCHEMA
}, extra=vol.ALLOW_EXTRA)

SERVICE_API_CALL = 'api_call'
ATTR_NAME = CONF_NAME
ATTR_PATH = CONF_PATH
ATTR_ARGS = "args"
EVENT_API_CALL_SUCCESS = "_".join((DOMAIN, SERVICE_API_CALL, "success"))

SERVICE_API_CALL_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): str,
    vol.Required(ATTR_PATH): vol.All(cv.ensure_list, [str]),
    vol.Optional(ATTR_ARGS): dict
})


async def async_setup(hass, config):
    """Set up the habitica service."""
    conf = config.get(DOMAIN, None)
    data = hass.data[DOMAIN] = {}
    websession = async_get_clientsession(hass)
    from habitipy.aio import HabitipyAsync

    class HAHabitipyAsync(HabitipyAsync):
        """Closure API class to hold session."""

        def __call__(self, **kwargs):
            return super().__call__(websession, **kwargs)

    for instance in conf:
        url = instance.get(CONF_URL, 'https://habitica.com')
        username = instance[CONF_API_USER]
        password = instance[CONF_API_KEY]
        name = instance.get(CONF_NAME)
        config_dict = dict(url=url, login=username, password=password)
        api = HAHabitipyAsync(config_dict)
        user = await api.user.get()
        if name is None:
            name = user['profile']['name']
        if name in data:
            _LOGGER.warning(
                "Same user is specified twice: %s", name)
        data[name] = api
        if CONF_SENSORS in instance:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass, "sensor", DOMAIN,
                    dict(name=name, sensors=instance[CONF_SENSORS]), config))

    async def handle_api_call(call):
        name = call.data[ATTR_NAME]
        path = call.data[ATTR_PATH]
        api = hass.data[DOMAIN].get(name)
        if api is None:
            _LOGGER.error(
                "API_CALL: User '%s' not configured", name)
            return
        try:
            for element in path:
                api = api[element]
        except KeyError:
            _LOGGER.error(
                "API_CALL: Path %s is invalid"
                " for api on '{%s}' element", path, element)
        kwargs = call.data.get(ATTR_ARGS, {})
        data = await api(**kwargs)
        hass.bus.fire(EVENT_API_CALL_SUCCESS, dict(
            name=name, path=path, data=data
        ))

    hass.services.async_register(
        DOMAIN, SERVICE_API_CALL,
        handle_api_call,
        schema=SERVICE_API_CALL_SCHEMA)
    return True
