"""Button to trigger force poll for Aquacell integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, INTEGRATION_DEVICE_NAME, SERVICE_POLL_NOW
from .coordinator import AquacellConfigEntry, AquacellCoordinator
from .entity import AquacellEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AquacellConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button for the Aquacell integration."""
    coordinator: AquacellCoordinator = config_entry.runtime_data
    entities: list[ButtonEntity] = [AquacellPollNowButton(coordinator, config_entry)]
    async_add_entities(entities)


class AquacellPollNowButton(AquacellEntity, ButtonEntity):
    """A button to trigger the poll_now service for the Aquacell integration."""

    _attr_name = "Poll now"
    _attr_unique_id = "aquacell_poll_now_button"
    _attr_translation_key = "poll_now"

    def __init__(
        self, coordinator: AquacellCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the force poll button."""
        super().__init__(
            coordinator, SERVICE_POLL_NOW, device_name=INTEGRATION_DEVICE_NAME
        )
        self._config_entry = config_entry

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_POLL_NOW,
            {},
            context=self._context,
        )
