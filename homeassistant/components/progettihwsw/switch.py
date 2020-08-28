"""Control switches."""

from datetime import timedelta

from ProgettiHWSW.relay import Relay

from homeassistant.components.switch import SwitchEntity

from . import setup_switch
from .const import DEFAULT_POLLING_INTERVAL_SEC, DOMAIN

SCAN_INTERVAL = timedelta(seconds=DEFAULT_POLLING_INTERVAL_SEC)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set the switch platform up (legacy)."""
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switches from a config entry."""
    board_api = hass.data[DOMAIN][config_entry.entry_id]
    relay_count = config_entry.data["relay_count"]
    switches = []

    for i in range(1, int(relay_count) + 1):
        switches.append(
            ProgettihwswSwitch(
                hass,
                config_entry,
                f"Relay #{i}",
                setup_switch(board_api, i, config_entry.data[f"relay_{str(i)}"]),
                i,
            )
        )

    async_add_entities(switches, True)


class ProgettihwswSwitch(SwitchEntity):
    """Represent a switch entity."""

    def __init__(self, hass, config_entry, name, switch: Relay, number: int):
        """Initialize the values."""
        self._switch = switch
        self._name = name
        self._state = None
        self._number = number

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        return self._switch.control(True)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        return self._switch.control(False)

    def toggle(self, **kwargs):
        """Toggle the state of switch."""
        return self._switch.toggle()

    @property
    def name(self):
        """Return the switch name."""
        return self._name

    @property
    def is_on(self):
        """Get switch state."""
        return self._state

    def update(self):
        """Update the state of switch."""
        self._switch.update()
        self._state = self._switch.is_on
