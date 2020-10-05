"""Support for Harmony Hub activities."""
import logging

from homeassistant.components.remote import ATTR_ACTIVITY
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATE_ACTIVITY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up harmony activity switches."""
    # TODO
    _LOGGER.warn("Loading the switch for harmony")

    device = hass.data[DOMAIN][entry.entry_id]
    activities = device.activity_names

    switches = []
    for activity in activities:
        switches.append(HarmonyActivitySwitch(activity, activity, device))

    async_add_entities(switches, True)


class HarmonyActivitySwitch(SwitchEntity):
    """Switch representation of a Harmony activity."""

    # TODO do we have all params
    def __init__(self, name, activity, device):
        """Initialize HarmonyActivitySwitch class."""
        self._name = name
        self._activity = activity
        self._device = device
        self._remove_signal_update = None

    @property
    def name(self):
        """Return the Harmony activity's name."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self._device.unique_id}-{self._activity}"

    # TODO private variables
    @property
    def is_on(self):
        """Return if the current activity is the one for this switch."""
        return self._device._current_activity == self._activity

    # @property
    # def available(self):
    # """Return True if we're connected to the Hub, otherwise False."""
    # return self._device.available

    async def async_turn_on(self, **kwargs):
        """Start this activity."""
        await self._device.async_turn_on(**{ATTR_ACTIVITY: self._activity})

    async def async_turn_off(self, **kwargs):
        """Stop this activity."""
        await self._device.async_turn_off()

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self._remove_signal_update = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ACTIVITY, self._update_callback
        )

    async def async_will_remove_from_hass(self):
        """Call when entity is removed from hass."""
        self._remove_signal_update()

    def _update_callback(self):
        # TODO was it just us
        self.async_write_ha_state()
