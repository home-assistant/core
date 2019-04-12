"""Support to interact with Wunderlist."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME, CONF_ACCESS_TOKEN)

REQUIREMENTS = ['wunderpy2==0.1.6']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'wunderlist'
CONF_CLIENT_ID = 'client_id'
CONF_LIST_NAME = 'list_name'
CONF_STARRED = 'starred'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


SERVICE_CREATE_TASK = 'create_task'

SERVICE_SCHEMA_CREATE_TASK = vol.Schema({
    vol.Required(CONF_LIST_NAME): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_STARRED): cv.boolean,
})


def setup(hass, config):
    """Set up the Wunderlist component."""
    conf = config[DOMAIN]
    client_id = conf.get(CONF_CLIENT_ID)
    access_token = conf.get(CONF_ACCESS_TOKEN)
    data = Wunderlist(access_token, client_id)
    if not data.check_credentials():
        _LOGGER.error("Invalid credentials")
        return False

    hass.services.register(DOMAIN, 'create_task', data.create_task)
    return True


class Wunderlist:
    """Representation of an interface to Wunderlist."""

    def __init__(self, access_token, client_id):
        """Create new instance of Wunderlist component."""
        import wunderpy2

        api = wunderpy2.WunderApi()
        self._client = api.get_client(access_token, client_id)

        _LOGGER.debug("Instance created")

    def check_credentials(self):
        """Check if the provided credentials are valid."""
        try:
            self._client.get_lists()
            return True
        except ValueError:
            return False

    def create_task(self, call):
        """Create a new task on a list of Wunderlist."""
        list_name = call.data.get(CONF_LIST_NAME)
        task_title = call.data.get(CONF_NAME)
        starred = call.data.get(CONF_STARRED)
        list_id = self._list_by_name(list_name)
        self._client.create_task(list_id, task_title, starred=starred)
        return True

    def _list_by_name(self, name):
        """Return a list ID by name."""
        lists = self._client.get_lists()
        tmp = [l for l in lists if l["title"] == name]
        if tmp:
            return tmp[0]["id"]
        return None
