"""Magic Home Lights integration."""
from datetime import timedelta

from magichome import MagicHomeApi
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval

DOMAIN = "magichome"
MAGICHOME_API = "magichome_api"
MAGICHOME_FORMAT = "magichome.{}"


SIGNAL_DELETE_ENTITY = "magichome_delete"
SIGNAL_UPDATE_ENTITY = "magichome_update"

SERVICE_FORCE_UPDATE = "force_update"
SERVICE_PULL_DEVICES = "pull_devices"

FACTORY = {
    "light": "light",
    "switch": "switch",
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Load magichome data."""
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    magichome = MagicHomeApi()
    hass.data[MAGICHOME_API] = magichome
    magichome.magichome_hub(username, password)
    hass.data[DOMAIN] = {"entities": {}}

    def load_devices(device_list):
        """Load new devices by device_list."""
        device_type_dict = {}
        for device in device_list:
            dev_type = device.device_type()
            if (
                dev_type in FACTORY
                and device.object_id() not in hass.data[DOMAIN]["entities"]
            ):
                ha_type = FACTORY[dev_type]
                device_type_dict.setdefault(dev_type, [])
                device_type_dict[ha_type].append(device.object_id())
                hass.data[DOMAIN]["entities"][device.object_id()] = None
        for ha_type, dev_ids in device_type_dict.items():
            discovery.load_platform(hass, ha_type, DOMAIN, {"dev_ids": dev_ids}, config)

    device_list = magichome.get_all_devices()
    load_devices(device_list)

    def poll_devices_update(event_time):
        """Check if accesstoken is expired and pull device list from server."""
        magichome.poll_devices_update()
        device_list = magichome.get_all_devices()
        load_devices(device_list)
        list_ids = []
        for device in device_list:
            list_ids.append(device.object_id())
        for dev_id in list(hass.data[DOMAIN]["entities"]):
            if dev_id not in list_ids:
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
        return MAGICHOME_FORMAT.format(self.magichome.object_id())

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
