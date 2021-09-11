"""Support for Minut Point binary sensors."""
import logging

from pypoint import EVENTS

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_COLD,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SOUND,
    DOMAIN,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import MinutPointEntity
from .const import DOMAIN as POINT_DOMAIN, POINT_DISCOVERY_NEW, SIGNAL_WEBHOOK

_LOGGER = logging.getLogger(__name__)


DEVICES = {
    "alarm": {"icon": "mdi:alarm-bell"},
    "battery": {"device_class": DEVICE_CLASS_BATTERY},
    "button_press": {"icon": "mdi:gesture-tap-button"},
    "cold": {"device_class": DEVICE_CLASS_COLD},
    "connectivity": {"device_class": DEVICE_CLASS_CONNECTIVITY},
    "dry": {"icon": "mdi:water"},
    "glass": {"icon": "mdi:window-closed-variant"},
    "heat": {"device_class": DEVICE_CLASS_HEAT},
    "moisture": {"device_class": DEVICE_CLASS_MOISTURE},
    "motion": {"device_class": DEVICE_CLASS_MOTION},
    "noise": {"icon": "mdi:volume-high"},
    "sound": {"device_class": DEVICE_CLASS_SOUND},
    "tamper_old": {"icon": "mdi:shield-alert"},
    "tamper": {"icon": "mdi:shield-alert"},
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Point's binary sensors based on a config entry."""

    async def async_discover_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[POINT_DOMAIN][config_entry.entry_id]
        async_add_entities(
            (
                MinutPointBinarySensor(client, device_id, device_name)
                for device_name in DEVICES
                if device_name in EVENTS
            ),
            True,
        )

    async_dispatcher_connect(
        hass, POINT_DISCOVERY_NEW.format(DOMAIN, POINT_DOMAIN), async_discover_sensor
    )


class MinutPointBinarySensor(MinutPointEntity, BinarySensorEntity):
    """The platform class required by Home Assistant."""

    def __init__(self, point_client, device_id, device_name):
        """Initialize the binary sensor."""
        super().__init__(
            point_client,
            device_id,
            DEVICES[device_name].get("device_class"),
        )
        self._device_name = device_name
        self._async_unsub_hook_dispatcher_connect = None
        self._events = EVENTS[device_name]
        self._is_on = None

    async def async_added_to_hass(self):
        """Call when entity is added to HOme Assistant."""
        await super().async_added_to_hass()
        self._async_unsub_hook_dispatcher_connect = async_dispatcher_connect(
            self.hass, SIGNAL_WEBHOOK, self._webhook_event
        )

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        await super().async_will_remove_from_hass()
        if self._async_unsub_hook_dispatcher_connect:
            self._async_unsub_hook_dispatcher_connect()

    async def _update_callback(self):
        """Update the value of the sensor."""
        if not self.is_updated:
            return
        if self._events[0] in self.device.ongoing_events:
            self._is_on = True
        else:
            self._is_on = None
        self.async_write_ha_state()

    @callback
    def _webhook_event(self, data, webhook):
        """Process new event from the webhook."""
        if self.device.webhook != webhook:
            return
        _type = data.get("event", {}).get("type")
        _device_id = data.get("event", {}).get("device_id")
        if _type not in self._events or _device_id != self.device.device_id:
            return
        _LOGGER.debug("Received webhook: %s", _type)
        if _type == self._events[0]:
            self._is_on = True
        if _type == self._events[1]:
            self._is_on = None
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        if self.device_class == DEVICE_CLASS_CONNECTIVITY:
            # connectivity is the other way around.
            return not self._is_on
        return self._is_on

    @property
    def name(self):
        """Return the display name of this device."""
        return f"{self._name} {self._device_name.capitalize()}"

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return DEVICES[self._device_name].get("icon")

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"point.{self._id}-{self._device_name}"
