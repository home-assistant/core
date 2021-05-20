"""Support for Harmony Hub activities."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .connection_state import ConnectionStateMixin
from .const import DOMAIN, HARMONY_DATA
from .data import HarmonyData
from .subscriber import HarmonyCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up harmony activity switches."""
    data = hass.data[DOMAIN][entry.entry_id][HARMONY_DATA]
    activities = data.activities

    switches = []
    for activity in activities:
        _LOGGER.debug("creating switch for activity: %s", activity)
        name = f"{entry.data[CONF_NAME]} {activity['label']}"
        switches.append(HarmonyActivitySwitch(name, activity, data))

    async_add_entities(switches, True)


class HarmonyActivitySwitch(ConnectionStateMixin, SwitchEntity):
    """Switch representation of a Harmony activity."""

    def __init__(self, name: str, activity: dict, data: HarmonyData):
        """Initialize HarmonyActivitySwitch class."""
        super().__init__()
        self._name = name
        self._activity_name = activity["label"]
        self._activity_id = activity["id"]
        self._data = data

    @property
    def name(self):
        """Return the Harmony activity's name."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"activity_{self._activity_id}"

    @property
    def device_info(self):
        """Return device info."""
        return self._data.device_info(DOMAIN)

    @property
    def is_on(self):
        """Return if the current activity is the one for this switch."""
        _, activity_name = self._data.current_activity
        return activity_name == self._activity_name

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
        await self._data.async_start_activity(self._activity_name)

    async def async_turn_off(self, **kwargs):
        """Stop this activity."""
        await self._data.async_power_off()

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""

        callbacks = {
            "connected": self.async_got_connected,
            "disconnected": self.async_got_disconnected,
            "activity_starting": self._async_activity_update,
            "activity_started": self._async_activity_update,
            "config_updated": None,
        }

        self.async_on_remove(self._data.async_subscribe(HarmonyCallback(**callbacks)))

    @callback
    def _async_activity_update(self, activity_info: tuple):
        self.async_write_ha_state()
