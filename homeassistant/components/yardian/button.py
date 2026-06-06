"""Support for Yardian buttons."""

from datetime import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .coordinator import YardianConfigEntry, YardianUpdateCoordinator
from .entity import YardianEntity

REFRESH_DELAY = 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YardianConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yardian button platform."""
    coordinator = entry.runtime_data

    async_add_entities([YardianStopButton(coordinator)])


class YardianStopButton(YardianEntity, ButtonEntity):
    """Representation of a Yardian Stop All Irrigation button."""

    _attr_has_entity_name = True
    _attr_translation_key = "stop_irrigation"

    def __init__(self, coordinator: YardianUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.client = coordinator.controller

        # Use the guaranteed string yid for the unique ID
        self._attr_unique_id = f"{coordinator.yid}_stop_all"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.client.stop_irrigation()

        # Schedule the refresh 3 seconds later without blocking the execution path
        async_call_later(self.hass, REFRESH_DELAY, self._async_delayed_refresh)

    @callback
    def _async_delayed_refresh(self, _now: datetime) -> None:
        """Refresh the coordinator data after a delay."""
        self.hass.async_create_task(self.coordinator.async_request_refresh())
