"""Support for Goal Zero Yeti Switches."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME

from . import YetiEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN, SWITCH_DICT


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Goal Zero Yeti switch."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    switches = [
        YetiSwitch(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            switch_name,
            entry.entry_id,
        )
        for switch_name in SWITCH_DICT
    ]
    async_add_entities(switches, True)


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

        self._condition_name = SWITCH_DICT[switch_name]

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._name} {self._condition_name}"

    @property
    def unique_id(self):
        """Return the unique id of the switch."""
        return f"{self._server_unique_id}/{self._condition_name}"

    @property
    def is_on(self):
        """Return state of the switch."""
        if self.api.data:
            return self.api.data[self._condition]
        return None

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
