"""Support for Harmony Hub activities."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME

from .connection_state import ConnectionStateMixin
from .const import DOMAIN
from .data import HarmonyData
from .subscriber import HarmonyCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up harmony activity switches."""
    data = hass.data[DOMAIN][entry.entry_id]
    activities = data.activity_names

    switches = []
    for activity in activities:
        _LOGGER.debug("creating switch for activity: %s", activity)
        name = f"{entry.data[CONF_NAME]} {activity}"
        switches.append(HarmonyActivitySwitch(name, activity, data))

    async_add_entities(switches, True)


class HarmonyActivitySwitch(ConnectionStateMixin, SwitchEntity):
    """Switch representation of a Harmony activity."""

    def __init__(self, name: str, activity: str, data: HarmonyData):
        """Initialize HarmonyActivitySwitch class."""
        super().__init__()
        self._name = name
        self._activity = activity
        self._data = data

    @property
    def name(self):
        """Return the Harmony activity's name."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self._data.unique_id}-{self._activity}"

    @property
    def is_on(self):
        """Return if the current activity is the one for this switch."""
        _, activity_name = self._data.current_activity
        return activity_name == self._activity

    @property
    def should_poll(self):
        """Return that we shouldn't be polled."""
        return False

    @property
    def available(self):
        """Return True if we're connected to the Hub, otherwise False."""
        return self._data.available

    async def async_turn_on(self, **kwargs):
        """Start this activity."""
        await self._data.async_start_activity(self._activity)

    async def async_turn_off(self, **kwargs):
        """Stop this activity."""
        await self._data.async_power_off()

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""

        callbacks = {
            "connected": self.got_connected,
            "disconnected": self.got_disconnected,
            "activity_starting": self._activity_update,
            "activity_started": self._activity_update,
            "config_updated": None,
        }

        self.async_on_remove(self._data.async_subscribe(HarmonyCallback(**callbacks)))

    def _activity_update(self, activity_info: tuple):
        self.async_write_ha_state()
