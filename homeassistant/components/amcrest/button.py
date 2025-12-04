"""Support for Amcrest Buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .models import AmcrestConfiguredDevice

# Define button types
BUTTON_TYPES: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="start_tour",
        name="Start Tour",
        icon="mdi:camera-control",
    ),
)

BUTTON_KEYS: list[str] = [desc.key for desc in BUTTON_TYPES]


# Platform setup for config flow
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amcrest buttons for a config entry."""
    device = config_entry.runtime_data.device
    coordinator = config_entry.runtime_data.coordinator
    entities = [
        AmcrestCoordinatedButton(device.name, device, coordinator, description)
        for description in BUTTON_TYPES
    ]
    async_add_entities(entities, True)


class AmcrestCoordinatedButton(CoordinatorEntity, ButtonEntity):
    """Representation of an Amcrest Camera Button tied to DataUpdateCoordinator."""

    def __init__(
        self,
        name: str,
        device: AmcrestConfiguredDevice,
        coordinator: DataUpdateCoordinator,
        entity_description: ButtonEntityDescription,
    ) -> None:
        """Initialize button."""
        CoordinatorEntity.__init__(self, coordinator)
        ButtonEntity.__init__(self)
        self.entity_description = entity_description
        self._device = device
        self._api = device.api
        self._attr_device_info = device.device_info
        self._attr_name = f"{name} {entity_description.name}"

        # Use serial number for unique ID if available, otherwise fall back to device name
        identifier = device.serial_number if device.serial_number else device.name
        self._attr_unique_id = f"{identifier}_{entity_description.key}"

    async def async_press(self) -> None:
        """Press the button - execute the button action."""
        key = self.entity_description.key
        if key == "start_tour":
            await self._api.async_tour(start=True)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Use coordinator availability and check if device is online
        return self.coordinator.data is not None and bool(
            self.coordinator.data.get("online", False)
        )
