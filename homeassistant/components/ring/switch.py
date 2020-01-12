"""This component provides HA switch support for Ring Door Bell/Chimes."""
from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.dt as dt_util

from . import DATA_RING_STICKUP_CAMS, DOMAIN, SIGNAL_UPDATE_RING

_LOGGER = logging.getLogger(__name__)

SIREN_ICON = "mdi:alarm-bell"


# It takes a few seconds for the API to correctly return an update indicating
# that the changes have been made. Once we request a change (i.e. a light
# being turned on) we simply wait for this time delta before we allow
# updates to take place.

SKIP_UPDATES_DELAY = timedelta(seconds=5)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create the switches for the Ring devices."""
    cameras = hass.data[DATA_RING_STICKUP_CAMS]
    switches = []
    for device in cameras:
        if device.has_capability("siren"):
            switches.append(SirenSwitch(device))

    async_add_entities(switches, True)


class BaseRingSwitch(SwitchDevice):
    """Represents a switch for controlling an aspect of a ring device."""

    def __init__(self, device, device_type):
        """Initialize the switch."""
        self._device = device
        self._device_type = device_type
        self._unique_id = f"{self._device.id}-{self._device_type}"
        self._disp_disconnect = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._disp_disconnect = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_RING, self._update_callback
        )

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        if self._disp_disconnect:
            self._disp_disconnect()
            self._disp_disconnect = None

    @callback
    def _update_callback(self):
        """Call update method."""
        _LOGGER.debug("Updating Ring sensor %s (callback)", self.name)
        self.async_schedule_update_ha_state(True)

    @property
    def name(self):
        """Name of the device."""
        return f"{self._device.name} {self._device_type}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def should_poll(self):
        """Update controlled via the hub."""
        return False

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.id)},
            "sw_version": self._device.firmware,
            "name": self._device.name,
            "model": self._device.kind,
            "manufacturer": "Ring",
        }


class SirenSwitch(BaseRingSwitch):
    """Creates a switch to turn the ring cameras siren on and off."""

    def __init__(self, device):
        """Initialize the switch for a device with a siren."""
        super().__init__(device, "siren")
        self._no_updates_until = dt_util.utcnow()
        self._siren_on = False

    def _set_switch(self, new_state):
        """Update switch state, and causes Home Assistant to correctly update."""
        self._device.siren = new_state
        self._siren_on = new_state > 0
        self._no_updates_until = dt_util.utcnow() + SKIP_UPDATES_DELAY
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._siren_on

    def turn_on(self, **kwargs):
        """Turn the siren on for 30 seconds."""
        self._set_switch(1)

    def turn_off(self, **kwargs):
        """Turn the siren off."""
        self._set_switch(0)

    @property
    def icon(self):
        """Return the icon."""
        return SIREN_ICON

    def update(self):
        """Update state of the siren."""
        if self._no_updates_until > dt_util.utcnow():
            _LOGGER.debug("Skipping update...")
            return
        self._siren_on = self._device.siren > 0
