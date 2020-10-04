"""Support for Harmony Hub activities."""
import logging

from homeassistant.components.remote import ATTR_ACTIVITY
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up harmony activity switches."""
    # TODO
    _LOGGER.warn("Loading the switch for harmony")

    device = hass.data[DOMAIN][entry.entry_id]
    activities = device.activity_names

    switches = []
    for activity in activities:
        switches.append(
            HarmonyActivitySwitch(
                activity + "-switch", "TODO" + activity, activity, device
            )
        )

    async_add_entities(switches, True)


class HarmonyActivitySwitch(SwitchEntity):
    """Switch representation of a Harmony activity."""

    # TODO do we have all params
    def __init__(self, name, unique_id, activity, remote):
        """Initialize HarmonyActivitySwitch class."""
        self._name = name
        self._unique_id = unique_id
        self._activity = activity
        self._remote = remote

    # TODO private variables
    @property
    def is_on(self):
        """Return if the current activity is the one for this switch."""
        return self._remote._current_activity == self._activity

    async def async_turn_on(self, **kwargs):
        """Start this activity."""
        self._remote.async_turn_on(**{ATTR_ACTIVITY: self.activity})

    async def async_turn_off(self, **kwargs):
        """Stop this activity."""
        self._remote.async_turn_off()
