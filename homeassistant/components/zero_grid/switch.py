"""Entities for ZeroGrid."""

from homeassistant.components.switch import SwitchEntity


class EnableLoadControlSwitch(SwitchEntity):
    """Switch to enable/disable load control."""

    def __init__(self, hass):
        self._hass = hass
        self._attr_name = "Enable Load Control"
        self._attr_unique_id = "enable_load_control"
        self._attr_is_on = False

    @property
    def is_on(self):
        return self._attr_is_on

    async def async_turn_on(self, **kwargs):
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._attr_is_on = False
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    async_add_entities([EnableLoadControlSwitch()])
