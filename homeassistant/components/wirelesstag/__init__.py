"""Support for Wireless Sensor Tags."""

import logging

from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol
from wirelesstagpy import WirelessTags
from wirelesstagpy.exceptions import WirelessTagsException

from homeassistant.components import persistent_notification
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SIGNAL_BINARY_EVENT_UPDATE, SIGNAL_TAG_UPDATE

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "wirelesstag_notification"
NOTIFICATION_TITLE = "Wireless Sensor Tag Setup"

DEFAULT_ENTITY_NAMESPACE = "wirelesstag"

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
        func_name = f"arm_{switch.entity_description.key}"
        if (arm_func := getattr(self.api, func_name)) is not None:
            arm_func(switch.tag_id, switch.tag_manager_mac)

    def disarm(self, switch):
        """Disarm entity sensor monitoring."""
        func_name = f"disarm_{switch.entity_description.key}"
        if (disarm_func := getattr(self.api, func_name)) is not None:
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
                except Exception as ex:  # noqa: BLE001
                    _LOGGER.error(
                        "Unable to handle tag update: %s error: %s",
                        str(tag),
                        str(ex),
                    )

        self.api.start_monitoring(push_callback)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
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
        persistent_notification.create(
            hass,
            f"Error: {ex}<br />Please restart hass after fixing this.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    return True
