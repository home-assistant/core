"""Support for Fluss Devices."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlussDataUpdateCoordinator
from .entity import FlussEntity

_LOGGER = logging.getLogger(__name__)

type FlussConfigEntry = ConfigEntry[FlussDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fluss Devices, filtering out any invalid payloads."""
    coordinator = entry.runtime_data
    devices = coordinator.data

    async_add_entities(FlussButton(coordinator, device_id, device) for device_id, device in devices.items())


class FlussButton(FlussEntity, ButtonEntity):
    """Representation of a Fluss button device."""


    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.api.async_trigger_device(self.device_id)

