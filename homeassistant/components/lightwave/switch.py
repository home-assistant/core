"""Support for LightwaveRF switches."""
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_NAME

from . import LIGHTWAVE_LINK


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Find and return LightWave switches."""
    if not discovery_info:
        return

    switches = []
    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in discovery_info.items():
        name = device_config[CONF_NAME]
        switches.append(LWRFSwitch(name, device_id, lwlink))

    async_add_entities(switches)


class LWRFSwitch(SwitchDevice):
    """Representation of a LightWaveRF switch."""

    def __init__(self, name, device_id, lwlink):
        """Initialize LWRFSwitch entity."""
        self._name = name
        self._device_id = device_id
        self._state = None
        self._lwlink = lwlink

    @property
    def should_poll(self):
        """No polling needed for a LightWave light."""
        return False

    @property
    def name(self):
        """Lightwave switch name."""
        return self._name

    @property
    def is_on(self):
        """Lightwave switch is on state."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the LightWave switch on."""
        self._state = True
        self._lwlink.turn_on_switch(self._device_id, self._name)
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the LightWave switch off."""
        self._state = False
        self._lwlink.turn_off(self._device_id, self._name)
        self.async_schedule_update_ha_state()
