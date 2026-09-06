"""Support for Watergate switches."""

from typing import Any, override

from watergate_local_api import WatergateApiException

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WatergateConfigEntry, WatergateDataCoordinator
from .entity import WatergateEntity

ENTITY_NAME = "auto_shut_off"
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Watergate switch entity."""
    async_add_entities([SonicAutoShutOffSwitch(config_entry.runtime_data)])


class SonicAutoShutOffSwitch(WatergateEntity, SwitchEntity):
    """Switch to enable or disable the auto-shut-off feature."""

    _attr_translation_key = "auto_shut_off"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: WatergateDataCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, ENTITY_NAME)

    @property
    @override
    def is_on(self) -> bool:
        """Return whether auto shut-off is enabled."""
        return self.coordinator.data.auto_shut_off.enabled

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto shut-off."""
        try:
            await self._api_client.async_update_auto_shut_off(enabled=True)
        except WatergateApiException as exc:
            raise HomeAssistantError("Failed to update auto shut-off") from exc
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto shut-off."""
        try:
            await self._api_client.async_update_auto_shut_off(enabled=False)
        except WatergateApiException as exc:
            raise HomeAssistantError("Failed to update auto shut-off") from exc
        await self.coordinator.async_request_refresh()
