"""Integration for Redgtech switches."""

import logging
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import STATE_ON, STATE_OFF
from .const import DOMAIN
from .coordinator import RedgtechDataUpdateCoordinator, RedgtechDevice, RedgtechConfigEntry
from redgtech_api.api import RedgtechConnectionError, RedgtechAuthError
from homeassistant.exceptions import HomeAssistantError, ConfigEntryError
from homeassistant.helpers.entity import DeviceInfo
from aiohttp import ClientError

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, config_entry: RedgtechConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switch platform."""

    coordinator = config_entry.runtime_data

    async_add_entities(RedgtechSwitch(coordinator, device) for device in coordinator.data)

class RedgtechSwitch(CoordinatorEntity[RedgtechDataUpdateCoordinator], SwitchEntity):
    """Representation of a Redgtech switch."""

    def __init__(self, coordinator: RedgtechDataUpdateCoordinator, device: RedgtechDevice) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.device = device
        self._attr_unique_id = f"redgtech_{device.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            manufacturer="Redgtech",
            model="Switch Model"
        )
    
    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self.device.name

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.device.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.set_device_state(self.device.id, True)
            self.device.state = STATE_ON
            self.async_write_ha_state()
        except ConfigEntryError as e:
            _LOGGER.error("Failed to turn on switch %s: %s", self.device.name, e)
            raise HomeAssistantError(f"Failed to turn on switch {self.device.name}: {e}") from e
        except RedgtechConnectionError as e:
            _LOGGER.error("Network error while turning on switch %s: %s", self.device.name, e)
            raise HomeAssistantError(f"Network error while turning on switch {self.device.name}: {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while turning on switch %s: %s", self.device.name, e)
            raise HomeAssistantError(f"Unexpected error while turning on switch {self.device.name}: {e}") from e

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.set_device_state(self.device.id, False)
            self.device.state = STATE_OFF
            self.async_write_ha_state()
        except ConfigEntryError as e:
            _LOGGER.error("Failed to turn off switch %s: %s", self.device.name, e)
            raise HomeAssistantError(f"Failed to turn off switch {self.device.name}: {e}") from e
        except RedgtechConnectionError as e:
            _LOGGER.error("Network error while turning off switch %s: %s", self.device.name, e)
            raise HomeAssistantError(f"Network error while turning off switch {self.device.name}: {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while turning off switch %s: %s", self.device.name, e)
            raise HomeAssistantError(f"Unexpected error while turning off switch {self.device.name}: {e}") from e
