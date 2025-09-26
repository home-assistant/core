"""Switch platform for Watts Vision integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from visionpluspython.models import SwitchDevice

from . import WattsVisionConfigEntry
from .const import UPDATE_DELAY_AFTER_COMMAND
from .coordinator import WattsVisionCoordinator
from .entity import WattsVisionEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattsVisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Watts Vision switch entities from a config entry."""

    coordinator: WattsVisionCoordinator = entry.runtime_data["coordinator"]

    entities = []
    for device in coordinator.data.values():
        if isinstance(device, SwitchDevice):
            entities.append(WattsVisionSwitch(coordinator, device))
            _LOGGER.debug("Created switch entity for device %s", device.device_id)

    if entities:
        async_add_entities(entities, update_before_add=True)
        _LOGGER.info("Added %d switch entities", len(entities))


class WattsVisionSwitch(WattsVisionEntity, SwitchEntity):
    """Watts Vision switch device as a switch entity."""

    def __init__(
        self,
        coordinator: WattsVisionCoordinator,
        device: SwitchDevice,
    ) -> None:
        """Initialize the switch entity."""

        super().__init__(coordinator, device.device_id)
        self._device = device
        self._device_id = device.device_id
        self._attr_name = None

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        device = self.coordinator.data.get(self._device_id)
        if isinstance(device, SwitchDevice):
            return device.is_turned_on
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device = self.coordinator.data.get(self._device_id)
        if not isinstance(device, SwitchDevice):
            return {}

        return {"device_type": device.device_type, "room_name": device.room_name}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.client.set_switch_state(self._device_id, True)
            _LOGGER.debug("Successfully turned on switch %s", self._attr_name)

            await asyncio.sleep(UPDATE_DELAY_AFTER_COMMAND)
            await self.coordinator.async_refresh_device(self._device_id)

        except RuntimeError as err:
            _LOGGER.error("Error turning on switch %s: %s", self._attr_name, err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.client.set_switch_state(self._device_id, False)
            _LOGGER.debug("Successfully turned off switch %s", self._attr_name)

            await asyncio.sleep(UPDATE_DELAY_AFTER_COMMAND)
            await self.coordinator.async_refresh_device(self._device_id)

        except RuntimeError as err:
            _LOGGER.error("Error turning off switch %s: %s", self._attr_name, err)
