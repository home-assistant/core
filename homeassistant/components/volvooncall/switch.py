"""Support for Volvo heater."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, VolvoEntity, VolvoUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure binary_sensors from a config entry created in the integrations UI."""
    volvo_data = hass.data[DOMAIN][config_entry.entry_id].volvo_data
    for instrument in volvo_data.instruments:
        if instrument.component == "switch":
            discovery_info = (
                instrument.vehicle.vin,
                instrument.component,
                instrument.attr,
                instrument.slug_attr,
            )

            async_add_entities(
                [VolvoSwitch(hass.data[DOMAIN][config_entry.entry_id], *discovery_info)]
            )


class VolvoSwitch(VolvoEntity, SwitchEntity):
    """Representation of a Volvo switch."""

    def __init__(
        self,
        coordinator: VolvoUpdateCoordinator,
        vin: str,
        component: str,
        attribute: str,
        slug_attr: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(vin, component, attribute, slug_attr, coordinator)

    @property
    def is_on(self):
        """Determine if switch is on."""
        return self.instrument.state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.instrument.turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.instrument.turn_off()
        await self.coordinator.async_request_refresh()
