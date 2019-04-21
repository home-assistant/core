"""Support for powering relays in a DoorBird video doorbell."""
import datetime
import logging

from homeassistant.components.switch import SwitchDevice

from . import DOMAIN as DOORBIRD_DOMAIN

DEPENDENCIES = ['doorbird']

_LOGGER = logging.getLogger(__name__)

IR_RELAY = '__ir_light__'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the DoorBird switch platform."""
    switches = []

    for doorstation in hass.data[DOORBIRD_DOMAIN]:
        relays = doorstation.device.info()['RELAYS']
        relays.append(IR_RELAY)

        for relay in relays:
            switch = DoorBirdSwitch(doorstation, relay)
            switches.append(switch)

    add_entities(switches)


class DoorBirdSwitch(SwitchDevice):
    """A relay in a DoorBird device."""

    def __init__(self, doorstation, relay):
        """Initialize a relay in a DoorBird device."""
        self._doorstation = doorstation
        self._relay = relay
        self._state = False
        self._assume_off = datetime.datetime.min

        if relay == IR_RELAY:
            self._time = datetime.timedelta(minutes=5)
        else:
            self._time = datetime.timedelta(seconds=5)

    @property
    def name(self):
        """Return the name of the switch."""
        if self._relay == IR_RELAY:
            return "{} IR".format(self._doorstation.name)

        return "{} Relay {}".format(self._doorstation.name, self._relay)

    @property
    def icon(self):
        """Return the icon to display."""
        return "mdi:lightbulb" if self._relay == IR_RELAY else "mdi:dip-switch"

    @property
    def is_on(self):
        """Get the assumed state of the relay."""
        return self._state

    def turn_on(self, **kwargs):
        """Power the relay."""
        if self._relay == IR_RELAY:
            self._state = self._doorstation.device.turn_light_on()
        else:
            self._state = self._doorstation.device.energize_relay(self._relay)

        now = datetime.datetime.now()
        self._assume_off = now + self._time

    def turn_off(self, **kwargs):
        """Turn off the relays is not needed. They are time-based."""
        raise NotImplementedError(
            "DoorBird relays cannot be manually turned off.")

    def update(self):
        """Wait for the correct amount of assumed time to pass."""
        if self._state and self._assume_off <= datetime.datetime.now():
            self._state = False
            self._assume_off = datetime.datetime.min
