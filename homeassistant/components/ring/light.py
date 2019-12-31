"""This component provides HA switch support for Ring Door Bell/Chimes."""
from datetime import timedelta
import logging

from homeassistant.components.light import Light
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.dt as dt_util

from . import DATA_RING_STICKUP_CAMS, SIGNAL_UPDATE_RING

_LOGGER = logging.getLogger(__name__)


# It takes a few seconds for the API to correctly return an update indicating
# that the changes have been made. Once we request a change (i.e. a light
# being turned on) we simply wait for this time delta before we allow
# updates to take place.

SKIP_UPDATES_DELAY = timedelta(seconds=5)

ON_STATE = "on"
OFF_STATE = "off"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the lights for the Ring devices."""
    cameras = hass.data[DATA_RING_STICKUP_CAMS]
    lights = []

    for device in cameras:
        if device.has_capability("light"):
            lights.append(RingLight(device))

    add_entities(lights, True)


class RingLight(Light):
    """Creates a switch to turn the ring cameras light on and off."""

    def __init__(self, device):
        """Initialize the light."""
        self._device = device
        self._unique_id = self._device.id
        self._light_on = False
        self._no_updates_until = dt_util.utcnow()

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(self.hass, SIGNAL_UPDATE_RING, self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        _LOGGER.debug("Updating Ring light %s (callback)", self.name)
        self.async_schedule_update_ha_state(True)

    @property
    def name(self):
        """Name of the light."""
        return f"{self._device.name} light"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def should_poll(self):
        """Update controlled via the hub."""
        return False

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._light_on

    def _set_light(self, new_state):
        """Update light state, and causes HASS to correctly update."""
        self._device.lights = new_state
        self._light_on = new_state == ON_STATE
        self._no_updates_until = dt_util.utcnow() + SKIP_UPDATES_DELAY
        self.async_schedule_update_ha_state(True)

    def turn_on(self, **kwargs):
        """Turn the light on for 30 seconds."""
        self._set_light(ON_STATE)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._set_light(OFF_STATE)

    def update(self):
        """Update current state of the light."""
        if self._no_updates_until > dt_util.utcnow():
            _LOGGER.debug("Skipping update...")
            return

        self._light_on = self._device.lights == ON_STATE
