"""Support for LightwaveRF switches."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME

from . import LIGHTWAVE_LINK


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Find and return LightWave switches."""
    if not discovery_info:
        return

    switches = []
    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in discovery_info.items():
        name = device_config[CONF_NAME]
        switches.append(LWRFSwitch(name, device_id, lwlink))

    async_add_entities(switches)


class LWRFSwitch(SwitchEntity):
    """Representation of a LightWaveRF switch."""

    _attr_should_poll = False

    def __init__(self, name, device_id, lwlink):
        """Initialize LWRFSwitch entity."""
        self._attr_name = name
        self._device_id = device_id
        self._lwlink = lwlink

    async def async_turn_on(self, **kwargs):
        """Turn the LightWave switch on."""
        self._attr_is_on = True
        self._lwlink.turn_on_switch(self._device_id, self._attr_name)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the LightWave switch off."""
        self._attr_is_on = False
        self._lwlink.turn_off(self._device_id, self._attr_name)
        self.async_write_ha_state()
