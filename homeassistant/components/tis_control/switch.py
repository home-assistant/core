"""Switch platform for TIS Control."""

from __future__ import annotations

from typing import Any

from TISApi.api import TISApi
from TISApi.components.switch.base_switch import TISAPISwitch
from TISApi.utils import async_get_switches

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TISConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TISConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TIS switches from a config entry."""

    # Retrieve the API instance that was created in the main __init__.py
    tis_api: TISApi = entry.runtime_data.api

    # Fetch all available switches from the TIS gateway.
    switch_dicts = await async_get_switches(tis_api)
    if not switch_dicts:
        return

    # Create an entity object for each switch found and add them to Home Assistant.
    async_add_entities(
        [TISSwitch(TISAPISwitch(tis_api, **sd)) for sd in switch_dicts],
        update_before_add=True,
    )


class TISSwitch(SwitchEntity):
    """Represents a TIS switch entity in Home Assistant."""

    def __init__(self, device_api: TISAPISwitch) -> None:
        """Initialize the switch entity."""
        self.device_api = device_api

        # Set the friendly name for the Home Assistant UI.
        self._attr_name = self.device_api.name
        self._attr_unique_id = self.device_api.unique_id
        self._attr_should_poll = False
        self._attr_available = True

        self._attr_is_on = self.device_api.is_on

    def _handle_update(self) -> None:
        """Handle state updates from the TISAPISwitch object."""
        self._attr_is_on = self.device_api.is_on
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to Home Assistant."""
        # Register the HASS update method as the callback
        self.device_api.register_callback(self._handle_update)

        # Request an initial state update from the device
        await self.device_api.request_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Attempt to turn the switch on and wait for the result.
        result = await self.device_api.turn_switch_on()

        if result:
            # Optimistic update: assume the command succeeded if we got an ack.
            self._attr_is_on = True
            self._attr_available = True
        else:
            # If no ack was received, the device is likely offline.
            self._attr_available = False

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # Send the 'off' packet and wait for an acknowledgement.
        result = await self.device_api.turn_switch_off()

        # Optimistically update the state based on whether the command was acknowledged.
        if result:
            self._attr_is_on = False
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()
