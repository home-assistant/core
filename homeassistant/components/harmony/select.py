"""Support for Harmony Hub select activities."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import ACTIVITY_POWER_OFF, DOMAIN, HARMONY_DATA
from .data import HarmonyData
from .entity import HarmonyEntity
from .subscriber import HarmonyCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up harmony activities select."""
    data = hass.data[DOMAIN][entry.entry_id][HARMONY_DATA]
    _LOGGER.debug("creating select for %s hub activities", entry.data[CONF_NAME])
    async_add_entities(
        [HarmonyActivitySelect(f"{entry.data[CONF_NAME]} Activities", data)]
    )


class HarmonyActivitySelect(HarmonyEntity, SelectEntity):
    """Select representation of a Harmony activities."""

    def __init__(self, name: str, data: HarmonyData) -> None:
        """Initialize HarmonyActivitySelect class."""
        super().__init__(data=data)
        self._data = data
        self._attr_unique_id = self._data.unique_id
        self._attr_device_info = self._data.device_info(DOMAIN)
        self._attr_name = name

    @property
    def icon(self):
        """Return a representative icon."""
        if not self.available or self.current_option == ACTIVITY_POWER_OFF:
            return "mdi:remote-tv-off"
        return "mdi:remote-tv"

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return [ACTIVITY_POWER_OFF] + sorted(self._data.activity_names)

    @property
    def current_option(self):
        """Return the current activity."""
        _, activity_name = self._data.current_activity
        return activity_name

    async def async_select_option(self, option: str) -> None:
        """Change the current activity."""
        await self._data.async_start_activity(option)

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
