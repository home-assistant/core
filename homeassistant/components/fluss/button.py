"""Support for Fluss Devices."""

import logging

from fluss_api.main import FlussApiClient

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FlussDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[FlussDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fluss Devices, filtering out any invalid payloads."""
    coordinator: FlussDataUpdateCoordinator = entry.runtime_data
    devices = coordinator.data.get("devices", [])

    entities: list[FlussButton] = []
    for device in devices:
        if not isinstance(device, dict):
            _LOGGER.warning("Skipping non-dict device: %s", device)
            continue

        device_id = device.get("deviceId")
        if device_id is None:
            _LOGGER.warning("Skipping Fluss device without deviceId: %s", device)
            continue

        entities.append(FlussButton(coordinator, device))

    async_add_entities(entities)


class FlussButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Fluss button device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FlussDataUpdateCoordinator, device: dict) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.device = device
        self._name = device.get("deviceName", "Unknown Device")
        self._attr_unique_id = str(device["deviceId"])

    @property
    def name(self) -> str:
        """Return name of the button."""
        return self._name

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.api.async_trigger_device(self.device["deviceId"])

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success
