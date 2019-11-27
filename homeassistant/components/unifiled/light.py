"""Support for Unifi Led lights."""
import logging

from homeassistant.components.light import ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light

from .const import DOMAIN, KEY_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Unifi LED platform."""

    # Assign configuration variables.
    # host = config_entry.data["host"]
    # port = config_entry.data["port"]
    # username = config_entry.data["username"]
    # password = config_entry.data["password"]

    # api = unifiled(host, port, username=username, password=password)

    # Verify that passed in configuration works
    # if not api.getloginstate():
    #    _LOGGER.error("Could not connect to unifiled controller")
    #    raise PlatformNotReady()

    api = hass.data[KEY_API][config_entry.entry_id]

    async_add_devices(UnifiLedLight(light, api) for light in api.getlights())


class UnifiLedLight(Light):
    """Representation of an unifiled Light."""

    def __init__(self, light, api):
        """Init Unifi LED Light."""

        self._api = api
        self._light = light
        self._name = light["name"]
        self._unique_id = light["id"]
        self._state = light["status"]["output"]
        self._available = light["isOnline"]
        self._brightness = self._api.convertfrom100to255(light["status"]["led"])
        self._features = SUPPORT_BRIGHTNESS

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def available(self):
        """Return the available state of this light."""
        return self._available

    @property
    def brightness(self):
        """Return the brightness name of this light."""
        return self._brightness

    @property
    def device_info(self):
        """Return the device info of this light."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "Ubiquiti Networks",
            "model": self._light["info"]["model"],
            "sw_version": self._light["info"]["version"],
        }

    @property
    def unique_id(self):
        """Return the unique id of this light."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Return the supported features of this light."""
        return self._features

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self._api.setdevicebrightness(
            self._unique_id,
            str(self._api.convertfrom255to100(kwargs.get(ATTR_BRIGHTNESS, 255))),
        )
        self._api.setdeviceoutput(self._unique_id, 1)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._api.setdeviceoutput(self._unique_id, 0)

    def update(self):
        """Update the light states."""
        self._state = self._api.getlightstate(self._unique_id)
        self._brightness = self._api.convertfrom100to255(
            self._api.getlightbrightness(self._unique_id)
        )
        self._available = self._api.getlightavailable(self._unique_id)
