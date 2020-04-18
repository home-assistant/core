"""Support for powering relays in a DoorBird video doorbell."""
import datetime
import logging

from homeassistant.components.switch import SwitchDevice
import homeassistant.util.dt as dt_util

from .const import DOMAIN, DOOR_STATION, DOOR_STATION_INFO
from .entity import DoorBirdEntity

_LOGGER = logging.getLogger(__name__)

IR_RELAY = "__ir_light__"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the DoorBird switch platform."""
    entities = []
    config_entry_id = config_entry.entry_id

    doorstation = hass.data[DOMAIN][config_entry_id][DOOR_STATION]
    doorstation_info = hass.data[DOMAIN][config_entry_id][DOOR_STATION_INFO]

    relays = doorstation_info["RELAYS"]
    relays.append(IR_RELAY)

    for relay in relays:
        switch = DoorBirdSwitch(doorstation, doorstation_info, relay)
        entities.append(switch)

    async_add_entities(entities)


class DoorBirdSwitch(DoorBirdEntity, SwitchDevice):
    """A relay in a DoorBird device."""

    def __init__(self, doorstation, doorstation_info, relay):
        """Initialize a relay in a DoorBird device."""
        super().__init__(doorstation, doorstation_info)
        self._doorstation = doorstation
        self._relay = relay
        self._state = False
        self._assume_off = datetime.datetime.min

        if relay == IR_RELAY:
            self._time = datetime.timedelta(minutes=5)
        else:
            self._time = datetime.timedelta(seconds=5)
        self._unique_id = f"{self._mac_addr}_{self._relay}"

    @property
    def unique_id(self):
        """Switch unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the switch."""
        if self._relay == IR_RELAY:
            return f"{self._doorstation.name} IR"

        return f"{self._doorstation.name} Relay {self._relay}"

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

        now = dt_util.utcnow()
        self._assume_off = now + self._time

    def turn_off(self, **kwargs):
        """Turn off the relays is not needed. They are time-based."""
        raise NotImplementedError("DoorBird relays cannot be manually turned off.")

    def update(self):
        """Wait for the correct amount of assumed time to pass."""
        if self._state and self._assume_off <= dt_util.utcnow():
            self._state = False
            self._assume_off = datetime.datetime.min
