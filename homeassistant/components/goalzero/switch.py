"""Support for Goal Zero Yeti Switches."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME

from . import YetiEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN, SWITCH_DICT


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Goal Zero Yeti switch."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        YetiSwitch(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            switch_name,
            entry.entry_id,
        )
        for switch_name in SWITCH_DICT
    )


class YetiSwitch(YetiEntity, SwitchEntity):
    """Representation of a Goal Zero Yeti switch."""

    def __init__(
        self,
        api,
        coordinator,
        name,
        switch_name,
        server_unique_id,
    ):
        """Initialize a Goal Zero Yeti switch."""
        super().__init__(api, coordinator, name, server_unique_id)
        self._condition = switch_name
        self._attr_name = f"{name} {SWITCH_DICT[switch_name]}"
        self._attr_unique_id = f"{server_unique_id}/{switch_name}"

    @property
    def is_on(self) -> bool:
        """Return state of the switch."""
        if self.api.data:
            return self.api.data[self._condition]
        return False

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        payload = {self._condition: 0}
        await self.api.post_state(payload=payload)
        self.coordinator.async_set_updated_data(data=payload)

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        payload = {self._condition: 1}
        await self.api.post_state(payload=payload)
        self.coordinator.async_set_updated_data(data=payload)
