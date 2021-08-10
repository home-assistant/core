"""Support for Wireless Sensor Tags."""
import logging

from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol
from wirelesstagpy import WirelessTags, WirelessTagsException

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_VOLTAGE,
    CONF_PASSWORD,
    CONF_USERNAME,
    ELECTRIC_POTENTIAL_VOLT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


# Strength of signal in dBm
ATTR_TAG_SIGNAL_STRENGTH = "signal_strength"
# Indicates if tag is out of range or not
ATTR_TAG_OUT_OF_RANGE = "out_of_range"
# Number in percents from max power of tag receiver
ATTR_TAG_POWER_CONSUMPTION = "power_consumption"


NOTIFICATION_ID = "wirelesstag_notification"
NOTIFICATION_TITLE = "Wireless Sensor Tag Setup"

DOMAIN = "wirelesstag"
DEFAULT_ENTITY_NAMESPACE = "wirelesstag"

# Template for signal - first parameter is tag_id,
# second, tag manager mac address
SIGNAL_TAG_UPDATE = "wirelesstag.tag_info_updated_{}_{}"

# Template for signal - tag_id, sensor type and
# tag manager mac address
SIGNAL_BINARY_EVENT_UPDATE = "wirelesstag.binary_event_updated_{}_{}_{}"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class WirelessTagPlatform:
    """Principal object to manage all registered in HA tags."""

    def __init__(self, hass, api):
        """Designated initializer for wirelesstags platform."""
        self.hass = hass
        self.api = api
        self.tags = {}
        self._local_base_url = None

    def load_tags(self):
        """Load tags from remote server."""
        self.tags = self.api.load_tags()
        return self.tags

    def arm(self, switch):
        """Arm entity sensor monitoring."""
        func_name = f"arm_{switch.sensor_type}"
        arm_func = getattr(self.api, func_name)
        if arm_func is not None:
            arm_func(switch.tag_id, switch.tag_manager_mac)

    def disarm(self, switch):
        """Disarm entity sensor monitoring."""
        func_name = f"disarm_{switch.sensor_type}"
        disarm_func = getattr(self.api, func_name)
        if disarm_func is not None:
            disarm_func(switch.tag_id, switch.tag_manager_mac)

    def start_monitoring(self):
        """Start monitoring push events."""

        def push_callback(tags_spec, event_spec):
            """Handle push update."""
            _LOGGER.debug(
                "Push notification arrived: %s, events: %s", tags_spec, event_spec
            )
            for uuid, tag in tags_spec.items():
                try:
                    tag_id = tag.tag_id
                    mac = tag.tag_manager_mac
                    _LOGGER.debug("Push notification for tag update arrived: %s", tag)
                    dispatcher_send(
                        self.hass, SIGNAL_TAG_UPDATE.format(tag_id, mac), tag
                    )
                    if uuid in event_spec:
                        events = event_spec[uuid]
                        for event in events:
                            _LOGGER.debug(
                                "Push notification for binary event arrived: %s", event
                            )
                            dispatcher_send(
                                self.hass,
                                SIGNAL_BINARY_EVENT_UPDATE.format(
                                    tag_id, event.type, mac
                                ),
                                tag,
                            )
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.error(
                        "Unable to handle tag update:\
                                %s error: %s",
                        str(tag),
                        str(ex),
                    )

        self.api.start_monitoring(push_callback)


def setup(hass, config):
    """Set up the Wireless Sensor Tag component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        wirelesstags = WirelessTags(username=username, password=password)

        platform = WirelessTagPlatform(hass, wirelesstags)
        platform.load_tags()
        platform.start_monitoring()
        hass.data[DOMAIN] = platform
    except (ConnectTimeout, HTTPError, WirelessTagsException) as ex:
        _LOGGER.error("Unable to connect to wirelesstag.net service: %s", str(ex))
        hass.components.persistent_notification.create(
            f"Error: {ex}<br />Please restart hass after fixing this.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    return True


class WirelessTagBaseSensor(Entity):
    """Base class for HA implementation for Wireless Sensor Tag."""

    def __init__(self, api, tag):
        """Initialize a base sensor for Wireless Sensor Tag platform."""
        self._api = api
        self._tag = tag
        self._uuid = self._tag.uuid
        self.tag_id = self._tag.tag_id
        self.tag_manager_mac = self._tag.tag_manager_mac
        self._name = self._tag.name
        self._state = None

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
        """Return formatted value.

        The default implementation formats principal value.
        """
        return self.decorate_value(self.principal_value)

    # pylint: disable=no-self-use
    def decorate_value(self, value):
        """Decorate input value to be well presented for end user."""
        return f"{value:.1f}"

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

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_BATTERY_LEVEL: int(self._tag.battery_remaining * 100),
            ATTR_VOLTAGE: f"{self._tag.battery_volts:.2f}{ELECTRIC_POTENTIAL_VOLT}",
            ATTR_TAG_SIGNAL_STRENGTH: f"{self._tag.signal_strength}{SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
            ATTR_TAG_OUT_OF_RANGE: not self._tag.is_in_range,
            ATTR_TAG_POWER_CONSUMPTION: f"{self._tag.power_consumption:.2f}{PERCENTAGE}",
        }
