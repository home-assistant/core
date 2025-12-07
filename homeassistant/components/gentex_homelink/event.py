"""Platform for Event integration."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, EVENT_PRESSED
from .coordinator import HomeLinkCoordinator, HomeLinkEventData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the entities for the binary sensor."""
    coordinator = config_entry.runtime_data.coordinator
    for device in coordinator.device_data:
        buttons = [
            HomeLinkEventEntity(b.id, b.name, device.id, device.name, coordinator)
            for b in device.buttons
        ]
        coordinator.buttons.extend(buttons)

    async_add_entities(coordinator.buttons)


# Updates are centralized by the coordinator.
PARALLEL_UPDATES = 0


class HomeLinkEventEntity(EventEntity):
    """Event Entity."""

    _attr_has_entity_name = True
    _attr_event_types = [EVENT_PRESSED]
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(
        self,
        id: str,
        param_name: str,
        device_id: str,
        device_name: str,
        coordinator: HomeLinkCoordinator,
    ) -> None:
        """Initialize the event entity."""

        self.id: str = id
        self._attr_name: str = param_name
        self._attr_unique_id: str = id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
        )
        self.coordinator = coordinator
        self.last_request_id: str | None = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_event_listener(
                self._handle_event_data_update, self.id
            )
        )

    @callback
    def _handle_event_data_update(self, update_data: HomeLinkEventData) -> None:
        """Update this button."""

        if update_data["requestId"] != self.last_request_id:
            self._trigger_event(EVENT_PRESSED)
            self.last_request_id = update_data["requestId"]

        self.async_write_ha_state()

    async def async_update(self):
        """Request early polling. Left intentionally blank because it's not possible in this implementation."""
