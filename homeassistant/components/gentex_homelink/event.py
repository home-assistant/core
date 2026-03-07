"""Platform for Event integration."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, EVENT_PRESSED
from .coordinator import HomeLinkConfigEntry, HomeLinkCoordinator, HomeLinkEventData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the entities for the event platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        HomeLinkEventEntity(coordinator, button.id, button.name, device.id, device.name)
        for device in coordinator.device_data
        for button in device.buttons
    )


# Updates are centralized by the coordinator.
PARALLEL_UPDATES = 0


class HomeLinkEventEntity(EventEntity):
    """Event Entity."""

    _attr_has_entity_name = True
    _attr_event_types = [EVENT_PRESSED]
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(
        self,
        coordinator: HomeLinkCoordinator,
        button_id: str,
        param_name: str,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the event entity."""

        self.button_id = button_id
        self._attr_name = param_name
        self._attr_unique_id = button_id
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
                self._handle_event_data_update, self.button_id
            )
        )

    @callback
    def _handle_event_data_update(self, update_data: HomeLinkEventData) -> None:
        """Update this button."""

        if update_data["requestId"] != self.last_request_id:
            self._trigger_event(EVENT_PRESSED)
            self.last_request_id = update_data["requestId"]
            self.async_write_ha_state()
