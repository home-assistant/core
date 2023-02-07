"""Support for Elgato button."""
from __future__ import annotations

from elgato import ElgatoError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ElgatoDataUpdateCoordinator
from .entity import ElgatoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elgato button based on a config entry."""
    coordinator: ElgatoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElgatoIdentifyButton(coordinator)])


class ElgatoIdentifyButton(ElgatoEntity, ButtonEntity):
    """Defines an Elgato identify button."""

    def __init__(self, coordinator: ElgatoDataUpdateCoordinator) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = ButtonEntityDescription(
            key="identify",
            name="Identify",
            icon="mdi:help",
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_unique_id = (
            f"{coordinator.data.info.serial_number}_{self.entity_description.key}"
        )

    async def async_press(self) -> None:
        """Identify the light, will make it blink."""
        try:
            await self.coordinator.client.identify()
        except ElgatoError as error:
            raise HomeAssistantError(
                "An error occurred while identifying the Elgato Light"
            ) from error
