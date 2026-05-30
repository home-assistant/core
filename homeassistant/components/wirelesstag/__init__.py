"""Support for Wireless Sensor Tags."""

import logging
from typing import TYPE_CHECKING

from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol
from wirelesstagpy import SensorTag, WirelessTags
from wirelesstagpy.binaryevent import BinaryEvent
from wirelesstagpy.exceptions import WirelessTagsException

from homeassistant.components import persistent_notification
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SIGNAL_BINARY_EVENT_UPDATE,
    SIGNAL_TAG_UPDATE,
    WIRELESSTAG_DATA,
)

if TYPE_CHECKING:
    from .switch import WirelessTagSwitch

_LOGGER = logging.getLogger(__name__)

# wirelesstagpy exposes the capacitive sensor under the "humidity" arm/disarm
# endpoints (ArmCapSensor). Water tags report that same sensor as "moisture"
# and have no dedicated arm_moisture/disarm_moisture method, so map it back to
# the shared endpoint.
ARM_KEY_OVERRIDES = {"moisture": "humidity"}

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

    def __init__(self, hass: HomeAssistant, api: WirelessTags) -> None:
        """Designated initializer for wirelesstags platform."""
        self.hass = hass
        self.api = api
        self.tags: dict[str, SensorTag] = {}
        self._local_base_url = None

    def load_tags(self) -> dict[str, SensorTag]:
        """Load tags from remote server."""
        self.tags = self.api.load_tags()
        return self.tags

    def arm(self, switch: WirelessTagSwitch) -> None:
        """Arm entity sensor monitoring."""
        self._set_monitoring(switch, "arm")

    def disarm(self, switch: WirelessTagSwitch) -> None:
        """Disarm entity sensor monitoring."""
        self._set_monitoring(switch, "disarm")

    def _set_monitoring(self, switch: WirelessTagSwitch, action: str) -> None:
        """Arm or disarm monitoring for the switch's sensor."""
        key = switch.entity_description.key
        func_name = f"{action}_{ARM_KEY_OVERRIDES.get(key, key)}"
        if (func := getattr(self.api, func_name, None)) is None:
            _LOGGER.error(
                "Cannot %s %s monitoring: wirelesstagpy has no %s method",
                action,
                key,
                func_name,
            )
            return
        func(switch.tag_id, switch.tag_manager_mac)

    def start_monitoring(self) -> None:
        """Start monitoring push events."""

        def push_callback(
            tags_spec: dict[str, SensorTag], event_spec: dict[str, list[BinaryEvent]]
        ) -> None:
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
    conf: ConfigType = config[DOMAIN]
    username: str = conf[CONF_USERNAME]
    password: str = conf[CONF_PASSWORD]

    try:
        wirelesstags = WirelessTags(username=username, password=password)

        platform = WirelessTagPlatform(hass, wirelesstags)
        platform.load_tags()
        platform.start_monitoring()
        hass.data[WIRELESSTAG_DATA] = platform
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
