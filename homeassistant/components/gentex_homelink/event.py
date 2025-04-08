"""Platform for BinarySensor integration."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Import keeps mypy happy but is a circular reference otherwise
    from .coordinator import HomeLinkCoordinator  # noqa: F401

import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_OFF, EVENT_PRESSED, EVENT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the entities for the binary sensor."""
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities(coordinator.buttons)


class HomeLinkEventEntity(CoordinatorEntity["HomeLinkCoordinator"], EventEntity):
    """Event Entity."""

    _attr_has_entity_name = True
    _attr_event_types = [
        EVENT_PRESSED,
        EVENT_OFF,
    ]
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(self, id, param_name, device_id, device_name, coordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, context=id)

        self.id = id
        name = param_name
        self._attr_name = name
        self._attr_unique_id = id
        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, device_id)
            },
            name=device_name,
        )

        self.name = name
        self.unique_id = id
        self.last_request_id = None
        self.button_off_task: asyncio.Task[Any] | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update this button."""
        if self.id not in self.coordinator.data:
            # Not for us
            return
        # Handles debounce case - if we're pressed again, and we have an active stop timer, cancel the previous timer and restart it
        if (
            self.state_attributes["event_type"] == EVENT_PRESSED
            and self.button_off_task
        ):
            self.button_off_task.cancel()
            self.button_off_task = asyncio.create_task(self.button_off())
            return

        # If this is the first press, set to off before setting pressed

        if self.last_request_id is None:
            self._trigger_event(EVENT_OFF)

        latest_update = self.coordinator.data[self.id]
        # Set button to pressed and then schedule the turnoff
        if latest_update["requestId"] != self.last_request_id:
            self._trigger_event(EVENT_PRESSED)
            self.last_request_id = latest_update["requestId"]
            self.button_off_task = asyncio.create_task(self.button_off())

        self.async_write_ha_state()

    async def button_off(self):
        """Wait for the specific time then turn the pressed button off."""
        await asyncio.sleep(EVENT_TIMEOUT)
        self._trigger_event(EVENT_OFF)
        self.button_off_task = None
        self.async_write_ha_state()
