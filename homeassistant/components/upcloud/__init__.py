"""Support for UpCloud."""
from datetime import timedelta
import logging

import upcloud_api
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
    STATE_PROBLEM,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from homeassistant.util import dt

_LOGGER = logging.getLogger(__name__)

ATTR_CORE_NUMBER = "core_number"
ATTR_HOSTNAME = "hostname"
ATTR_MEMORY_AMOUNT = "memory_amount"
ATTR_STATE = "state"
ATTR_TITLE = "title"
ATTR_UUID = "uuid"
ATTR_ZONE = "zone"

CONF_SERVERS = "servers"

DATA_UPCLOUD = "data_upcloud"
DOMAIN = "upcloud"

DEFAULT_COMPONENT_NAME = "UpCloud {}"
DEFAULT_COMPONENT_DEVICE_CLASS = "power"

UPCLOUD_PLATFORMS = ["binary_sensor", "switch"]

SCAN_INTERVAL = timedelta(seconds=60)

SIGNAL_UPDATE_UPCLOUD = "upcloud_update"

STATE_MAP = {"error": STATE_PROBLEM, "started": STATE_ON, "stopped": STATE_OFF}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the UpCloud component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    manager = upcloud_api.CloudManager(username, password)

    try:
        manager.authenticate()
        hass.data[DATA_UPCLOUD] = UpCloud(manager)
    except upcloud_api.UpCloudAPIError:
        _LOGGER.error("Authentication failed")
        return False

    def upcloud_update(event_time):
        """Call UpCloud to update information."""
        _LOGGER.debug("Updating UpCloud component")
        hass.data[DATA_UPCLOUD].update()
        dispatcher_send(hass, SIGNAL_UPDATE_UPCLOUD)

    # Call the UpCloud API to refresh data
    upcloud_update(dt.utcnow())
    track_time_interval(hass, upcloud_update, scan_interval)

    return True


class UpCloud:
    """Handle all communication with the UpCloud API."""

    def __init__(self, manager):
        """Initialize the UpCloud connection."""
        self.data = {}
        self.manager = manager

    def update(self):
        """Update data from UpCloud API."""
        self.data = {server.uuid: server for server in self.manager.get_servers()}


class UpCloudServerEntity(Entity):
    """Entity class for UpCloud servers."""

    def __init__(self, upcloud, uuid):
        """Initialize the UpCloud server entity."""
        self._upcloud = upcloud
        self.uuid = uuid
        self.data = None
        self._unsub_handlers = []

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return self.uuid

    @property
    def name(self):
        """Return the name of the component."""
        try:
            return DEFAULT_COMPONENT_NAME.format(self.data.title)
        except (AttributeError, KeyError, TypeError):
            return DEFAULT_COMPONENT_NAME.format(self.uuid)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._unsub_handlers.append(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_UPCLOUD, self._update_callback
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Invoke unsubscription handlers."""
        for unsub in self._unsub_handlers:
            unsub()
        self._unsub_handlers.clear()

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def icon(self):
        """Return the icon of this server."""
        return "mdi:server" if self.is_on else "mdi:server-off"

    @property
    def state(self):
        """Return state of the server."""
        try:
            return STATE_MAP.get(self.data.state)
        except AttributeError:
            return None

    @property
    def is_on(self):
        """Return true if the server is on."""
        return self.state == STATE_ON

    @property
    def device_class(self):
        """Return the class of this server."""
        return DEFAULT_COMPONENT_DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return the state attributes of the UpCloud server."""
        return {
            x: getattr(self.data, x, None)
            for x in (
                ATTR_UUID,
                ATTR_TITLE,
                ATTR_HOSTNAME,
                ATTR_ZONE,
                ATTR_STATE,
                ATTR_CORE_NUMBER,
                ATTR_MEMORY_AMOUNT,
            )
        }

    def update(self):
        """Update data of the UpCloud server."""
        self.data = self._upcloud.data.get(self.uuid)
