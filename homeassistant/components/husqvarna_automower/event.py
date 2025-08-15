"""Creates the event entities for supported mowers."""

from collections.abc import Callable

from aioautomower.model import SingleMessageData

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutomowerConfigEntry
from .const import ERROR_KEYS
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

PARALLEL_UPDATES = 1

ATTR_SEVERITY = "severity"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"
ATTR_DATE_TIME = "date_time"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Automower message event entities.

    Entities are created dynamically based on messages received from the API,
    but only for mowers that support message events.
    """
    coordinator = config_entry.runtime_data
    entity_registry = er.async_get(hass)

    restored_mowers = {
        entry.unique_id.removesuffix("_message")
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == EVENT_DOMAIN
    }

    async_add_entities(
        AutomowerMessageEventEntity(mower_id, coordinator)
        for mower_id in restored_mowers
        if mower_id in coordinator.data
    )

    @callback
    def _handle_message(msg: SingleMessageData) -> None:
        if msg.id in restored_mowers:
            return

        restored_mowers.add(msg.id)
        async_add_entities([AutomowerMessageEventEntity(msg.id, coordinator)])

    coordinator.api.register_single_message_callback(_handle_message)


class AutomowerMessageEventEntity(AutomowerBaseEntity, EventEntity):
    """EventEntity for Automower message events."""

    entity_description: EventEntityDescription
    _message_cb: Callable[[SingleMessageData], None]
    _attr_translation_key = "message"
    _attr_event_types = ERROR_KEYS

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Initialize Automower message event entity."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = f"{mower_id}_message"

    @callback
    def _handle(self, msg: SingleMessageData) -> None:
        """Handle a message event from the API and trigger the event entity if it matches the entity's mower ID."""
        if msg.id != self.mower_id:
            return
        message = msg.attributes.message
        self._trigger_event(
            message.code,
            {
                ATTR_SEVERITY: message.severity,
                ATTR_LATITUDE: message.latitude,
                ATTR_LONGITUDE: message.longitude,
                ATTR_DATE_TIME: message.time,
            },
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback when entity is added to hass."""
        await super().async_added_to_hass()
        self.coordinator.api.register_single_message_callback(self._handle)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister WebSocket callback when entity is removed."""
        self.coordinator.api.unregister_single_message_callback(self._handle)
