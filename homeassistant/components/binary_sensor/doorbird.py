"""Support for reading binary states from a DoorBird video doorbell."""
import asyncio
import datetime
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.doorbird import DOMAIN as DOORBIRD_DOMAIN
from homeassistant.components.http import HomeAssistantView

DEPENDENCIES = ['doorbird']

_LOGGER = logging.getLogger(__name__)

API_URL = "/api/" + DOORBIRD_DOMAIN

SENSOR_DOORBELL = "doorbell"

SENSOR_TYPES = {
    SENSOR_DOORBELL: {
        "name": "Doorbell Ringing",
        "icon": {
            True: "bell-ring",
            False: "bell",
            None: "bell-outline"
        },
        "time": datetime.timedelta(seconds=5),
        "instance": None
    }
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the DoorBird binary sensor component."""
    device = hass.data.get(DOORBIRD_DOMAIN)

    # Provide an endpoint for the device to call to trigger events
    hass.http.register_view(DoorbirdRequestView())
    _LOGGER.debug("Registered DoorBird request view")

    # This will make HA the only service that gets doorbell events
    url = hass.config.api.base_url + API_URL + "/" + SENSOR_DOORBELL
    device.reset_notifications()
    device.subscribe_notification(SENSOR_DOORBELL, url)
    _LOGGER.debug("Configured DoorBird notifications")

    doorbell = DoorBirdBinarySensor(device, SENSOR_DOORBELL)
    SENSOR_TYPES[SENSOR_DOORBELL]["instance"] = doorbell
    add_devices([doorbell], True)
    _LOGGER.info("Added DoorBird binary sensor")


class DoorBirdBinarySensor(BinarySensorDevice):
    """A binary sensor of a DoorBird device."""

    def __init__(self, device, sensor_type):
        """Initialize a binary sensor on a DoorBird device."""
        self._device = device
        self._sensor_type = sensor_type
        self._assume_off = datetime.datetime.now()

    def push(self):
        """Handle a message from the device."""
        now = datetime.datetime.now()
        time = SENSOR_TYPES[self._sensor_type]["time"]
        self._assume_off = now + time

    @property
    def name(self):
        """Get the name of the sensor."""
        return SENSOR_TYPES[self._sensor_type]["name"]

    @property
    def icon(self):
        """Get an icon to display."""
        state_icon = SENSOR_TYPES[self._sensor_type]["icon"][self.is_on]
        return "mdi:{}".format(state_icon)

    @property
    def is_on(self):
        """Get the state of the binary sensor."""
        return self._assume_off > datetime.datetime.now()


class DoorbirdRequestView(HomeAssistantView):
    """Provide a page for the device to call."""

    url = API_URL
    name = API_URL[1:].replace("/", ":")
    extra_urls = [API_URL + "/{sensor}"]

    @asyncio.coroutine
    def get(self, request, sensor):
        """Handle the incoming message from the device."""
        try:
            sensor_type = SENSOR_TYPES[sensor]
        except KeyError:
            _LOGGER.warning("DoorBird requested invalid sensor %s", sensor)
            return "ERROR"

        try:
            sensor_instance = sensor_type["instance"]
        except KeyError:
            _LOGGER.warning("DoorBird sensor %s does not exist", sensor)
            return "ERROR"

        sensor_instance.push()
        return "OK"
