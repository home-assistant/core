"""Support for Harmony Hub activities."""
import logging

from homeassistant.components.remote import ATTR_ACTIVITY
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONNECTION_UPDATE_ACTIVITY, DOMAIN, SIGNAL_UPDATE_ACTIVITY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up harmony activity switches."""
    device = hass.data[DOMAIN][entry.entry_id]
    activities = device.activity_names

    switches = []
    for activity in activities:
        switches.append(HarmonyActivitySwitch(activity, device))

    async_add_entities(switches, True)


class HarmonyActivitySwitch(SwitchEntity):
    """Switch representation of a Harmony activity."""

    def __init__(self, activity, device):
        """Initialize HarmonyActivitySwitch class."""
        self._activity = activity
        self._device = device
        self._state = False
        self._available = False
        self._dispatcher_disconnectors = []

    @property
    def name(self):
        """Return the Harmony activity's name."""
        return self._activity

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self._device.unique_id}-{self._activity}"

    @property
    def is_on(self):
        """Return if the current activity is the one for this switch."""
        return self._state

    @property
    def should_poll(self):
        """Return that we shouldn't be polled."""
        return False

    @property
    def available(self):
        """Return True if we're connected to the Hub, otherwise False."""
        return self._available

    async def async_turn_on(self, **kwargs):
        """Start this activity."""
        await self._device.async_turn_on(**{ATTR_ACTIVITY: self._activity})

    async def async_turn_off(self, **kwargs):
        """Stop this activity."""
        await self._device.async_turn_off()

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self._dispatcher_disconnectors.append(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_ACTIVITY, self._update_activity_callback
            )
        )

        self._dispatcher_disconnectors.append(
            async_dispatcher_connect(
                self.hass, CONNECTION_UPDATE_ACTIVITY, self._update_connection_callback
            )
        )

    async def async_will_remove_from_hass(self):
        """Call when entity is removed from hass."""
        for disconnector in self._dispatcher_disconnectors:
            disconnector()

    def _update_activity_callback(self, data):
        old_state = self._state
        if data["current_activity"] == self._activity:
            self._state = True
        else:
            self._state = False

        if self._state != old_state:
            self.async_write_ha_state()

    def _update_connection_callback(self, data):
        old_state = self._available
        self._available = data["available"]
        if self._available != old_state:
            self.async_write_ha_state()
