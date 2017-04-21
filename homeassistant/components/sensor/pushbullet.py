"""
PushBullet platform for sensor component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.pushbullet/
"""
import logging
import voluptuous as vol


from homeassistant.const import (CONF_API_KEY, CONF_MONITORED_CONDITIONS)
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pushbullet.py==0.10.0']

SENSOR_TYPES = {
    'application_name': ['Application name'],
    'body': ['Body'],
    'notification_id': ['Notification ID'],
    'notification_tag': ['Notification tag'],
    'package_name': ['Package name'],
    'receiver_email': ['Receiver email'],
    'sender_email': ['Sender email'],
    'source_device_iden': ['Sender device ID'],
    'title': ['Title'],
    'type': ['Type']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(
        CONF_MONITORED_CONDITIONS,
        default=['title', 'body']): vol.All(
            cv.ensure_list, vol.Length(min=1),
            [vol.In(SENSOR_TYPES.keys())]
            ),
    vol.Required(CONF_API_KEY): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the PushBullet notification service."""
    from pushbullet import PushBullet
    from pushbullet import InvalidKeyError
    try:
        pushbullet = PushBullet(config.get(CONF_API_KEY))
    except InvalidKeyError:
        _LOGGER.error("Wrong API key supplied." \
                "Get it at https://www.pushbullet.com/account")
        return None
    # Create a common data provider
    pbprovider = PushBulletNotificationProvider(pushbullet)
    # Create a device for each property
    devices = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        devices.append(PushBulletNotificationSensor(pbprovider, sensor_type))
    add_devices(devices)


class PushBulletNotificationSensor(Entity):
    """Fetches data via a filter from the common pushbullet provider."""

    def __init__(self, pb, element):
        """Initialize the service."""
        self.pushbullet = pb
        self._element = element
        self._state = None
        self._state_attributes = None

    def update(self):
        """Fetches the latest data from the sensor.

        This will fetch the 'sensor reading' into self._state but also all
        attributes into self._state_attributes."""
        try:
            self._state = self.pushbullet.data[self._element]
            self._state_attributes = self.pushbullet.data
        except (KeyError, TypeError):
            pass

    @property
    def name(self):
        """Returns the name of the sensor."""
        return "Pushbullet " + self._element

    @property
    def state(self):
        """Returns the current state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Returns all known attributes of the sensor."""
        return self._state_attributes


class PushBulletNotificationProvider():
    """Provider for an account, leading to one or more sensors."""

    def __init__(self, pb):
        """Starts to retrieve pushes from the given Pushbullet instance."""
        import threading
        self.pushbullet = pb
        self._data = None
        self.thread = threading.Thread(target=self.retrieve_pushes)
        self.thread.daemon = True
        self.thread.start()

    def on_push(self, data):
        """Method to update the current data.

        Currently only monitors pushes but might be extended to monitor
        different kinds of Pushbullet events."""
        if data["type"] == "push":
            self._data = data["push"]

    @property
    def data(self):
        """The current data stored in the provider."""
        return self._data

    def retrieve_pushes(self):
        """The method to run the daemon thread in.

        Spawns a new Listener and links it to self.on_push."""
        from pushbullet import Listener
        self.listener = Listener(account=self.pushbullet,
                                 on_push=self.on_push)
        _LOGGER.debug("getting pushes")
        try:
            self.listener.run_forever()
        finally:
            self.listener.close()
