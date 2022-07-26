"""Support for Volvo heater."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import VolvoEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a Volvo switch."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSwitch(hass, *discovery_info)])


class VolvoSwitch(VolvoEntity, SwitchEntity):
    """Representation of a Volvo switch."""

    def __init__(
        self, hass: HomeAssistant, vin, component, attribute, slug_attr, coordinator
    ):
        """Initialize the switch."""
        VolvoEntity.__init__(
            self, hass, vin, component, attribute, slug_attr, coordinator
        )

        self._attr_is_on = self.instrument.state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.instrument.state
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.instrument.turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.instrument.turn_off()
        await self.coordinator.async_request_refresh()
