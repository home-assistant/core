"""
Wireless Sensor Tags platform support.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/wirelesstag/
"""
import logging

from requests.exceptions import HTTPError, ConnectTimeout
import voluptuous as vol
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_VOLTAGE, CONF_USERNAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['wirelesstagpy==0.3.0']

_LOGGER = logging.getLogger(__name__)

# tag type value is int - I need more info how to interpret it
ATTR_TAG_TYPE = 'type'
# comment assigned to tag, value is string
ATTR_TAG_COMMENT = 'comment'
# is tag alive
ATTR_TAG_IS_ALIVE = 'alive'
# straight of signal in dBm
ATTR_TAG_SIGNAL_STRAIGHT = 'signal_straight'
# beep options (5 times, 10 times, 15 times etc)
ATTR_TAG_BEEP_DURATION = 'beep_duration'
# indicates if tag is out of range or not - valye, Bool
ATTR_TAG_OUT_OF_RANGE = 'out_of_range'
# hw revision version
ATTR_TAG_HW_REVISION = 'revision'
# tag fw version
ATTR_TAG_FW_VERSION = 'version'
# number in percents from max power of tag receiver
ATTR_TAG_POWER_CONSUMPTION = 'power_consumption'


NOTIFICATION_ID = 'wirelesstag_notification'
NOTIFICATION_TITLE = "Wireless Sensor Tag Setup"

DOMAIN = 'wirelesstag'
DEFAULT_ENTITY_NAMESPACE = 'wirelesstag'

WIRELESSTAG_TYPE_13BIT = 13
WIRELESSTAG_TYPE_ALSPRO = 26
WIRELESSTAG_TYPE_WATER = 32
WIRELESSTAG_TYPE_WEMO_DEVICE = 82

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


class WirelessTagPlatform:
    """Principal object to manage all registered in HA tags."""

    def __init__(self, hass, api):
        """Designated initializer for wirelesstags platform."""
        self.hass = hass
        self.api = api
        self.entities = []
        self.binary_sensors = []  # binary sensors only
        self.tags = {}

    def load_tags(self):
        """Load tags from remote server."""
        self.tags = self.api.load_tags()
        return self.tags

    @property
    def use_celcius(self):
        """Indicate if unit of measure in celcius."""
        return self.api.use_celsius

    def arm(self, switch):
        """Arm entity sensor monitoring."""
        func_name = 'arm_{}'.format(switch.sensor_type)
        arm_func = getattr(self.api, func_name)
        if arm_func is not None:
            arm_func(switch.tag_id)

    def disarm(self, switch):
        """Disarm entity sensor monitoring."""
        func_name = 'disarm_{}'.format(switch.sensor_type)
        disarm_func = getattr(self.api, func_name)
        if disarm_func is not None:
            disarm_func(switch.tag_id)

    def register_entity(self, entity):
        """Resiter new enity for local push notification."""
        _LOGGER.info("Registered entity for value update: - %s", entity)
        self.entities.append(entity)

    # pylint: disable=no-self-use
    def make_push_notitication(self, name, url, content):
        """Factory for notification config."""
        from wirelesstagpy import NotificationConfig
        return NotificationConfig(name, {
            'url': url, 'verb': 'POST',
            'content': content, 'disabled': False, 'nat': True})

    def install_push_notifications(self, binary_sensors):
        """Setup local push notification from tag manager."""
        self.binary_sensors = binary_sensors
        configs = []

        binary_url = self.binary_event_callback_url
        for event in self.binary_sensors:
            for state, name in event.binary_spec.items():
                content = ('{"type": "' + event.device_class +
                           '", "id":{' + str(event.tag_id_index_template) +
                           '}, "state": \"' + state + '\"}')
                config = self.make_push_notitication(name, binary_url, content)
                configs.append(config)

        content = ("{\"name\":\"{0}\",\"id\":{1},\"temp\":{2}," +
                   "\"cap\":{3},\"lux\":{4}}")
        update_url = self.update_callback_url
        update_config = self.make_push_notitication(
            'update', update_url, content)
        configs.append(update_config)

        result = self.api.install_push_notification(0, configs, True)
        if not result:
            self.hass.components.persistent_notification.create(
                "Error: failed to install local push notifications<br />",
                title="Wireless Sensor Tag Setup Local Push Notifications",
                notification_id="wirelesstag_failed_push_notification")
        else:
            _LOGGER.info("Installed push notifications for all tags.")

    @property
    def update_callback_url(self):
        """Return url for local push notifications(update event)."""
        return '{}/api/events/wirelesstag_update_tags'.format(
            self.hass.config.api.base_url)

    @property
    def binary_event_callback_url(self):
        """Return url for local push notifications(binary event)."""
        return '{}/api/events/wirelesstag_binary_event'.format(
            self.hass.config.api.base_url)

    def handle_update_tags_event(self, event):
        """Main entry to handle push event from wireless tag manager."""
        _LOGGER.info("push notification for update arrived: %s", event)
        for entity in self.entities:
            if event.data.get('id') == entity.tag_id:
                _LOGGER.info("Entity to update state: %s event data: %s",
                             entity, event.data)
                entity.update_tag_info(event)

    def handle_binary_event(self, event):
        """Handle push notifications for binary (on/off) events."""
        _LOGGER.info("Push notification for binary event arrived: %s", event)
        try:
            tag_id = event.data.get('id')
            event_type = event.data.get('type')
            for sensor in self.binary_sensors:
                if (tag_id == sensor.tag_id and
                        event_type == sensor.device_class):
                    sensor.on_binary_event(event)
        except Exception as ex:  # pylint: disable=W0703
            _LOGGER.error("Unable to handle binary event:\
                          %s error: %s", str(event), str(ex))


def setup(hass, config):
    """Set up the Wireless Sensor Tag component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        from wirelesstagpy import (WirelessTags, WirelessTagsException)
        wirelesstags = WirelessTags(username=username, password=password)

        platform = WirelessTagPlatform(hass, wirelesstags)
        platform.load_tags()
        hass.data[DOMAIN] = platform
    except (ConnectTimeout, HTTPError, WirelessTagsException) as ex:
        _LOGGER.error("Unable to connect to wirelesstag.net service: %s",
                      str(ex))
        hass.components.persistent_notification.create(
            "Error: {}<br />"
            "Please restart hass after fixing this."
            "".format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    # listen to custom event
    hass.bus.listen('wirelesstag_update_tags',
                    hass.data[DOMAIN].handle_update_tags_event)
    hass.bus.listen('wirelesstag_binary_event',
                    hass.data[DOMAIN].handle_binary_event)

    return True


class WirelessTagBaseSensor(Entity):
    """Base class for HA implementation for Wireless Sensor Tag."""

    def __init__(self, api, tag):
        """Initialize a base sensor for Wireless Sensor Tag platform."""
        self._api = api
        self._tag = tag
        self._uuid = self._tag.uuid
        self.tag_id = self._tag.tag_id
        self._name = self._tag.name
        self._state = None

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def principal_value(self):
        """Return base value.

        Subclasses need override based on type of sensor.
        """
        return 0

    def updated_state_value(self):
        """Default implementation formats princial value."""
        return self.decorate_value(self.principal_value)

    # pylint: disable=no-self-use
    def decorate_value(self, value):
        """Decorate input value to be well presented for end user."""
        return '{:.1f}'.format(value)

    @property
    def available(self):
        """Return True if entity is available."""
        return self._tag.is_alive

    def update(self):
        """Update state."""
        if not self.should_poll:
            return

        updated_tags = self._api.load_tags()
        updated_tag = updated_tags[self._uuid]
        if updated_tag is None:
            _LOGGER.error('Unable to update tag: "%s"', self.name)
            return

        self._tag = updated_tag
        self._state = self.updated_state_value()

    def update_tag_info(self, event):
        """Update sensor data on push notification event.

        Subclasses must ovverride - handler of push notification.
        """
        pass

    def on_binary_event(self, event):
        """Update sensor data on push notification binary event.

        Applicable for binary sensors only.
        Subclasses must ovverride - handler of push notification.
        """
        pass

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_BATTERY_LEVEL: self._tag.battery_remaining,
            ATTR_VOLTAGE: '{:.2f}V'.format(self._tag.battery_volts),
            ATTR_TAG_SIGNAL_STRAIGHT: '{}dBm'.format(
                self._tag.signal_straight),
            ATTR_TAG_OUT_OF_RANGE: not self._tag.is_in_range,
            ATTR_TAG_POWER_CONSUMPTION: '{:.2f}%'.format(
                self._tag.power_consumption)
        }
