"""This component provides HA switch support for Ring Door Bell/Chimes."""
from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchDevice

from . import DATA_RING

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

SIREN_ICON = 'mdi:alarm-bell'
LIGHT_ICON = 'mdi:track-light'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Ring device."""
    ring = hass.data[DATA_RING]
    logging.warning('setting up')
    switches = []

    for device in ring.stickup_cams:  # ring.stickup_cams is doing I/O
        if device.has_capability('siren'):
            switches.append(SirenSwitch(hass, device))
        if device.has_capability('light'):
            switches.append(LightSwitch(hass, device))

    add_entities(switches, True)


class BaseRingSwitch(SwitchDevice):
    """Represents a switch for controlling an aspect of a ring device"""
    def __init__(self, hass, device, device_type):
        self._device = device
        self._device_type = device_type
        self._unique_id = '{}-{}'.format(self._device.id, self._device_type)

    @property
    def name(self):
        """Name of the device."""
        return '{} {}'.format(self._device.name, self._device_type)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    def update(self):
        """Get the siren status from ring"""
        self._device.update()


class SirenSwitch(BaseRingSwitch):
    """Used to turn the ring cameras siren on and off"""
    def __init__(self, hass, device):
        BaseRingSwitch.__init__(self, hass, device, 'siren')
        self._on = False

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._on

    def turn_on(self, **kwargs):
        """Turn the siren on for 30 seconds."""
        self._on = True
        self._device.siren = 1

    def turn_off(self, **kwargs):
        """Turn the siren off"""
        self._on = False
        self._device.siren = 0

    def update(self):
        """Get the siren status from ring"""
        BaseRingSwitch.update(self)
        self._on = self._device.siren > 0

    @property
    def icon(self):
        """Return the icon."""
        return SIREN_ICON


class LightSwitch(BaseRingSwitch):
    """Used to turn the ring cameras light on and off"""
    def __init__(self, hass, device):
        BaseRingSwitch.__init__(self, hass, device, 'light')
        self._on = False

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._on

    def turn_on(self, **kwargs):
        """Turn the light on for 30 seconds."""
        self._on = True
        self._device.lights = 'on'

    def turn_off(self, **kwargs):
        """Turn the light off"""
        self._on = False
        self._device.lights = 'off'

    def update(self):
        """Get the light status from ring"""
        BaseRingSwitch.update(self)
        self._on = self._device.lights == 'on'

    @property
    def icon(self):
        """Return the icon."""
        return LIGHT_ICON
