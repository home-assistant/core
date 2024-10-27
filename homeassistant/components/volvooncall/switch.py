"""Support for Volvo heater."""

from __future__ import annotations

from typing import Any

from volvooncall.dashboard import Instrument

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VOLVO_DISCOVERY_NEW
from .coordinator import VolvoUpdateCoordinator
from .entity import VolvoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure binary_sensors from a config entry created in the integrations UI."""
    coordinator: VolvoUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    volvo_data = coordinator.volvo_data

    @callback
    def async_discover_device(instruments: list[Instrument]) -> None:
        """Discover and add a discovered Volvo On Call switch."""
        async_add_entities(
            VolvoSwitch(
                coordinator,
                instrument.vehicle.vin,
                instrument.component,
                instrument.attr,
                instrument.slug_attr,
            )
            for instrument in instruments
            if instrument.component == "switch"
        )

    async_discover_device([*volvo_data.instruments])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VOLVO_DISCOVERY_NEW, async_discover_device)
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.instrument.turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.instrument.turn_off()
        await self.coordinator.async_request_refresh()
