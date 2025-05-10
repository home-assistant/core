"""Integration for Redgtech switches."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import STATE_ON, STATE_OFF
from .const import DOMAIN
from .coordinator import RedgtechDataUpdateCoordinator, RedgtechDevice
from redgtech_api.api import RedgtechConnectionError, RedgtechAuthError
from homeassistant.exceptions import HomeAssistantError, ConfigEntryError
from homeassistant.helpers.entity import DeviceInfo, ToggleEntity
from homeassistant.helpers.restore_state import RestoreEntity

if TYPE_CHECKING:
    from . import RedgtechConfigEntry

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, config_entry: RedgtechConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switch platform."""
    coordinator: RedgtechDataUpdateCoordinator = config_entry.runtime_data
    async_add_entities(RedgtechSwitch(coordinator, device) for device in coordinator.data)

class RedgtechSwitch(ToggleEntity, RestoreEntity):
    """Representation of a Redgtech switch."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: RedgtechDataUpdateCoordinator, device: RedgtechDevice) -> None:
        """Initialize the switch."""
        self.coordinator = coordinator
        self.device = device
        self._attr_unique_id = f"redgtech_{device.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            manufacturer="Redgtech",
            model="Switch Model",
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.device.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_state(False)

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        new_state = not self.is_on
        await self._async_set_state(new_state)

    async def _async_set_state(self, state: bool) -> None:
        """Set the state of the switch."""
        try:
            await self.coordinator.api.set_switch_state(self.device.id, state, self.coordinator.access_token)
            self.device.state = STATE_ON if state else STATE_OFF
            self.async_write_ha_state()
        except RedgtechAuthError:
            await self.coordinator.renew_token()
            await self.coordinator.api.set_switch_state(self.device.id, state, self.coordinator.access_token)
            self.device.state = STATE_ON if state else STATE_OFF
            self.async_write_ha_state()
        except RedgtechConnectionError as e:
            raise ConfigEntryError("Failed to set switch state due to connection error") from e
        except Exception as e:
            raise HomeAssistantError("Unexpected error while setting switch state") from e

    async def async_added_to_hass(self) -> None:
        """Restore the previous state when added to Home Assistant."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self.device.state = STATE_ON if last_state.state == STATE_ON else STATE_OFF
            self.async_write_ha_state()
