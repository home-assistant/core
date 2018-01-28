"""
Support for UpCloud.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/upcloud/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['upcloud-api==0.3.9']

_LOGGER = logging.getLogger(__name__)

ATTR_CORE_NUMBER = 'core_number'
ATTR_HOSTNAME = 'hostname'
ATTR_MEMORY_AMOUNT = 'memory_amount'
ATTR_STATE = 'state'
ATTR_TITLE = 'title'
ATTR_UUID = 'uuid'
ATTR_ZONE = 'zone'

CONF_SERVERS = 'servers'

DATA_UPCLOUD = 'data_upcloud'
DOMAIN = 'upcloud'

DEFAULT_COMPONENT_NAME = 'UpCloud {}'
DEFAULT_COMPONENT_DEVICE_CLASS = 'power'

UPCLOUD_PLATFORMS = ['binary_sensor', 'switch']

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the UpCloud component."""
    import upcloud_api

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    manager = upcloud_api.CloudManager(username, password)

    try:
        manager.authenticate()
    except upcloud_api.UpCloudAPIError:
        _LOGGER.error("Authentication failed.")
        return False

    hass.data[DATA_UPCLOUD] = UpCloud(manager)
    hass.data[DATA_UPCLOUD].update()

    return True


class UpCloud(object):
    """Handle all communication with the UpCloud API."""

    def __init__(self, manager):
        """Initialize the UpCloud connection."""
        self.data = {}
        self.manager = manager

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from UpCloud API."""
        self.data = {
            server.uuid: server for server in self.manager.get_servers()
        }


class UpCloudServerMixin(object):
    """Common properties for UpCloud server components."""

    def __init__(self, upcloud, uuid):
        """Initialize a new UpCloud server mixin."""
        self._upcloud = upcloud
        self.uuid = uuid
        self.data = None

    @property
    def name(self):
        """Return the name of the component."""
        try:
            return DEFAULT_COMPONENT_NAME.format(self.data.title)
        except (AttributeError, KeyError, TypeError):
            return DEFAULT_COMPONENT_NAME.format(self.uuid)

    @property
    def icon(self):
        """Return the icon of this server."""
        return 'mdi:server' if self.is_on else 'mdi:server-off'

    @property
    def is_on(self):
        """Return true if the server is on."""
        try:
            return self.data.state == 'started'
        except AttributeError:
            return False

    @property
    def device_class(self):
        """Return the class of this server."""
        return DEFAULT_COMPONENT_DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the UpCloud server."""
        return {
            x: getattr(self.data, x, None)
            for x in (ATTR_UUID, ATTR_TITLE, ATTR_HOSTNAME, ATTR_ZONE,
                      ATTR_STATE, ATTR_CORE_NUMBER, ATTR_MEMORY_AMOUNT)
        }

    def update(self):
        """Update state of sensor."""
        self._upcloud.update()
        self.data = self._upcloud.data.get(self.uuid)
