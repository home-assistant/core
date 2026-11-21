"""Button platform for the Daikin Onecta integration."""

from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .entity import DaikinOnectaAccountEntity

PARALLEL_UPDATES = 1

BUTTON_DESCRIPTIONS = {
    "refresh": ButtonEntityDescription(
        key="refresh",
        translation_key="refresh",
        entity_category=EntityCategory.CONFIG,
    )
}


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

    entity_description = BUTTON_DESCRIPTIONS["refresh"]

    def __init__(self, coordinator: OnectaDataUpdateCoordinator) -> None:
        """Initialize the account refresh button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._account_id}_refresh"

    @property
    @override
    def available(self) -> bool:
        """Allow manual recovery even when the previous cloud refresh failed."""
        return True

    @override
    async def async_press(self) -> None:
        """Request an immediate account refresh."""
        refreshed = await self.coordinator.async_manual_refresh()
        if not refreshed or not self.coordinator.last_update_success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
            )
