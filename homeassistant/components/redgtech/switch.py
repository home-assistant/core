"""Integration for Redgtech switches."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import STATE_ON, STATE_OFF
from .const import DOMAIN
from .coordinator import RedgtechDataUpdateCoordinator, RedgtechDevice, RedgtechConfigEntry
from redgtech_api.api import RedgtechConnectionError, RedgtechAuthError
from homeassistant.exceptions import HomeAssistantError, ConfigEntryError
from homeassistant.helpers.entity import DeviceInfo, ToggleEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, config_entry: RedgtechConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switch platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(RedgtechSwitch(coordinator, device) for device in coordinator.data)

class RedgtechSwitch(ToggleEntity):
    """Representation of a Redgtech switch."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: RedgtechDataUpdateCoordinator, device: RedgtechDevice) -> None:
        """Initialize the switch."""
        self.coordinator = coordinator
        self.device = device
        self._attr_unique_id = device.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            manufacturer="Redgtech",
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.device.state == STATE_ON

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        new_state = not self.is_on    
        try:
            if not self.coordinator.access_token:
                await self.coordinator.login(self.coordinator.email, self.coordinator.password)

            await self.coordinator.api.set_switch_state(self.device.id, new_state, self.coordinator.access_token)
            self.device.state = STATE_ON if new_state else STATE_OFF
            self.async_write_ha_state()
        except RedgtechAuthError:
            try:
                await self.coordinator.renew_token()
                await self.coordinator.api.set_switch_state(self.device.id, new_state, self.coordinator.access_token)
                self.device.state = STATE_ON if new_state else STATE_OFF
                self.async_write_ha_state()
            except RedgtechAuthError as e:
                raise HomeAssistantError("Failed to set switch state due to authentication error") from e
        except RedgtechConnectionError as e:
            raise HomeAssistantError("conection error while setting switch state") from e
        except Exception as e:
            raise HomeAssistantError("Unexpected error while toggling switch state") from e
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if not self.is_on:
            await self.async_toggle()
        
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self.is_on:
            await self.async_toggle()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
