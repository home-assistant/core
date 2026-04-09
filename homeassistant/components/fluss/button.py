"""Support for Fluss button devices."""

from __future__ import annotations

from fluss_api import FlussApiClientError

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlussConfigEntry
from .entity import FlussEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fluss button entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        FlussButton(coordinator, device_id, device)
        for device_id, device in coordinator.data.items()
    )


class FlussButton(FlussEntity, ButtonEntity):
    """Representation of a Fluss button device."""

    _attr_name = None

    @property
    def icon(self) -> str:
        """Return the base icon for the configured icon type."""
        return self._base_icon

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.api.async_trigger_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain="fluss",
                translation_key="trigger_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
