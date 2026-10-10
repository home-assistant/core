"""Button platform for the Daikin Onecta integration."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .entity import DaikinOnectaAccountEntity
from .entity_descriptions import BUTTON_DESCRIPTIONS

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the account refresh button."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    async_add_entities([DaikinRefreshButton(coordinator)])


class DaikinRefreshButton(DaikinOnectaAccountEntity, ButtonEntity):
    """Button to request an immediate account data update."""

    def __init__(self, coordinator: OnectaDataUpdateCoordinator) -> None:
        """Initialize the account refresh button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_refresh"
        self.entity_description = BUTTON_DESCRIPTIONS["refresh"]

    @override
    async def async_press(self) -> None:
        """Request an immediate account refresh."""
        await self.coordinator.async_refresh()
        if not self.coordinator.last_update_success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
            )
