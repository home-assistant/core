"""Support for Volvo heater."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_KEY, VolvoEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Volvo switch."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSwitch(hass.data[DATA_KEY], *discovery_info)])


class VolvoSwitch(VolvoEntity, SwitchEntity):
    """Representation of a Volvo switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.instrument.state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.instrument.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.instrument.turn_off()
        self.async_write_ha_state()
