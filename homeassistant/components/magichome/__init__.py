"""Support for MagicHome Smart devices."""
from datetime import timedelta
import logging
from magichome import MagicHomeApi
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_PLATFORM
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval


_LOGGER = logging.getLogger(__name__)

CONF_COMPANY = "company"

DOMAIN = "magichome"
DATA_MAGICHOME = "data_magichome"

SIGNAL_DELETE_ENTITY = "magichome_delete"
SIGNAL_UPDATE_ENTITY = "magichome_update"

SERVICE_FORCE_UPDATE = "force_update"
SERVICE_PULL_DEVICES = "pull_devices"

MAGICHOME_TYPE_TO_HA = {
    "light": "light",
    "scene": "scene",
    "switch": "switch",
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_COMPANY, default="ZG001"): cv.string,
                vol.Optional(CONF_PLATFORM, default="ZG001"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up MagicHome Component."""
    magichome = MagicHomeApi()
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    company = config[DOMAIN][CONF_COMPANY]
    platform = config[DOMAIN][CONF_PLATFORM]

    hass.data[DATA_MAGICHOME] = magichome
    magichome.init(username, password, company, platform)
    hass.data[DOMAIN] = {"entities": {}}

    def load_devices(device_list):
        """Load new devices by device_list."""
        device_type_list = {}
        for device in device_list:
            dev_type = device.device_type()
            if (
                dev_type in MAGICHOME_TYPE_TO_HA
                and device.object_id() not in hass.data[DOMAIN]["entities"]
            ):
                ha_type = MAGICHOME_TYPE_TO_HA[dev_type]
                if ha_type not in device_type_list:
                    device_type_list[ha_type] = []
                device_type_list[ha_type].append(device.object_id())
                hass.data[DOMAIN]["entities"][device.object_id()] = None
        for ha_type, dev_ids in device_type_list.items():
            discovery.load_platform(hass, ha_type, DOMAIN, {"dev_ids": dev_ids}, config)

    device_list = magichome.get_all_devices()
    load_devices(device_list)

    def poll_devices_update(event_time):
        """Check if accesstoken is expired and pull device list from server."""
        _LOGGER.debug("Pull devices from MagicHome.")
        magichome.poll_devices_update()
        # Add new discover device.
        device_list = magichome.get_all_devices()
        load_devices(device_list)
        # Delete not exist device.
        newlist_ids = []
        for device in device_list:
            newlist_ids.append(device.object_id())
        for dev_id in list(hass.data[DOMAIN]["entities"]):
            if dev_id not in newlist_ids:
                dispatcher_send(hass, SIGNAL_DELETE_ENTITY, dev_id)
                hass.data[DOMAIN]["entities"].pop(dev_id)

    track_time_interval(hass, poll_devices_update, timedelta(minutes=5))

    hass.services.register(DOMAIN, SERVICE_PULL_DEVICES, poll_devices_update)

    def force_update(call):
        """Force all devices to pull data."""
        dispatcher_send(hass, SIGNAL_UPDATE_ENTITY)

    hass.services.register(DOMAIN, SERVICE_FORCE_UPDATE, force_update)

    return True


class MagicHomeDevice(Entity):
    """MagicHome base device."""

    def __init__(self, magichome):
        """Init MagicHome devices."""
        self.magichome = magichome

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        dev_id = self.magichome.object_id()
        self.hass.data[DOMAIN]["entities"][dev_id] = self.entity_id
        async_dispatcher_connect(self.hass, SIGNAL_DELETE_ENTITY, self._delete_callback)
        async_dispatcher_connect(self.hass, SIGNAL_UPDATE_ENTITY, self._update_callback)

    @property
    def object_id(self):
        """Return MagicHome device id."""
        return self.magichome.object_id()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return "magichome.{}".format(self.magichome.object_id())

    @property
    def name(self):
        """Return MagicHome device name."""
        return self.magichome.name()

    @property
    def available(self):
        """Return if the device is available."""
        return self.magichome.available()

    def update(self):
        """Refresh MagicHome device data."""
        self.magichome.update()

    @callback
    def _delete_callback(self, dev_id):
        """Remove this entity."""
        if dev_id == self.object_id:
            self.hass.async_create_task(self.async_remove())

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)
