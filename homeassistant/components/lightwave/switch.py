"""Support for LightwaveRF switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import LIGHTWAVE_LINK


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LightWave switch on."""
        self._attr_is_on = True
        self._lwlink.turn_on_switch(self._device_id, self._attr_name)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LightWave switch off."""
        self._attr_is_on = False
        self._lwlink.turn_off(self._device_id, self._attr_name)
        self.async_write_ha_state()
