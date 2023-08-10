"""Support for Harmony Hub activities."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HARMONY_DATA
from .data import HarmonyData
from .entity import HarmonyEntity
from .subscriber import HarmonyCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up harmony activity switches."""
    data = hass.data[DOMAIN][entry.entry_id][HARMONY_DATA]
    activities = data.activities

    switches = []
    for activity in activities:
        switches.append(HarmonyActivitySwitch(activity, data))

    async_add_entities(switches, True)


class HarmonyActivitySwitch(HarmonyEntity, SwitchEntity):
    """Switch representation of a Harmony activity."""

    def __init__(self, activity: dict, data: HarmonyData) -> None:
        """Initialize HarmonyActivitySwitch class."""
        super().__init__(data=data)
        self._activity_name = activity["label"]
        self._activity_id = activity["id"]
        self._attr_entity_registry_enabled_default = False
        self._attr_unique_id = f"activity_{self._activity_id}"
        self._attr_name = self._activity_name
        self._attr_device_info = self._data.device_info(DOMAIN)

    @property
    def is_on(self):
        """Return if the current activity is the one for this switch."""
        _, activity_name = self._data.current_activity
        return activity_name == self._activity_name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start this activity."""
        await self._data.async_start_activity(self._activity_name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop this activity."""
        await self._data.async_power_off()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.async_on_remove(
            self._data.async_subscribe(
                HarmonyCallback(
                    connected=self.async_got_connected,
                    disconnected=self.async_got_disconnected,
                    activity_starting=self._async_activity_update,
                    activity_started=self._async_activity_update,
                    config_updated=None,
                )
            )
        )

    @callback
    def _async_activity_update(self, activity_info: tuple):
        self.async_write_ha_state()
