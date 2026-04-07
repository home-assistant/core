"""Support for Fluss button devices."""

from __future__ import annotations

from fluss_api import FlussApiClientError

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlussConfigEntry, FlussDataUpdateCoordinator
from .entity import FlussEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fluss button entities from a config entry."""
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = []

    for device_id, device in coordinator.data.items():
        permissions = device.get("userPermissions", {})

        if permissions.get("canOpenMain"):
            entities.append(
                FlussOpenMainButton(coordinator, device_id, device)
            )

    async_add_entities(entities)


class FlussOpenMainButton(FlussEntity, ButtonEntity):
    """Button to open the main gate/door."""

    _attr_translation_key = "open_main"

    def __init__(
        self,
        coordinator: FlussDataUpdateCoordinator,
        device_id: str,
        device: dict,
    ) -> None:
        """Initialize the open main button."""
        super().__init__(coordinator, device_id, device, unique_id_suffix="open_main")

    @property
    def icon(self) -> str:
        """Return the icon based on configured icon type."""
        base = self._base_icon
        # Use an -open variant if it exists in mdi
        if self._icon_type in ("gate", "garage"):
            return f"{base}-open"
        return base

    async def async_press(self) -> None:
        """Handle the button press to open main."""
        try:
            await self.coordinator.api.async_open_device(self.device_id)
        except FlussApiClientError as err:
            raise HomeAssistantError(
                translation_domain="fluss",
                translation_key="open_failed",
                translation_placeholders={"error": str(err)},
            ) from err


