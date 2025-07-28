"""Creates the event entities for supported mowers."""

import logging

from aioautomower.model import Message, SingleMessageData

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.storage import Store

from . import AutomowerConfigEntry
from .const import DOMAIN, ERROR_KEYS
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

ATTR_SEVERITY = "severity"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"


_STORAGE_KEY = f"{DOMAIN}_message_event_seen"


EVENT_DESCRIPTIONS = [
    EventEntityDescription(
        key="message",
        translation_key="message",
        event_types=ERROR_KEYS,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Automower message event entities.

    Not all mowers support message events, so we create entities
    only for those that do. The entities are created dynamically
    based on the messages received from the API.
    """
    coordinator: AutomowerDataUpdateCoordinator = entry.runtime_data
    store: Store[dict[str, bool]] = Store(hass, 1, _STORAGE_KEY)
    seen_mowers: dict[str, bool] = await store.async_load() or {}

    # Mapping mower_id -> entity instance
    entities_by_mower_id: dict[str, AutomowerMessageEventEntity] = {}

    # Restore previously seen mowers
    for mower_id in seen_mowers:
        for description in EVENT_DESCRIPTIONS:
            entity = AutomowerMessageEventEntity(mower_id, coordinator, description)
            entities_by_mower_id[mower_id] = entity
            async_add_entities([entity])

    async def handle_new_message(message_data: SingleMessageData) -> None:
        mower_id = message_data.id

        if mower_id in entities_by_mower_id:
            entities_by_mower_id[mower_id].async_handle_new_message(message_data)
            return

        seen_mowers[mower_id] = True
        await store.async_save(seen_mowers)
        _LOGGER.debug("Creating message event entity for mower %s", mower_id)

        new_entities: list[AutomowerMessageEventEntity] = []
        for description in EVENT_DESCRIPTIONS:
            entity = AutomowerMessageEventEntity(mower_id, coordinator, description)
            entities_by_mower_id[mower_id] = entity
            new_entities.append(entity)

        async_add_entities(new_entities)
        for entity in new_entities:
            entity.async_handle_new_message(message_data)

        # Register a single global callback for all mower messages

    def _schedule_handle(msg_data: SingleMessageData) -> None:
        """Schedule the async handler for new messages."""
        hass.async_create_task(handle_new_message(msg_data))

    coordinator.api.register_single_message_callback(_schedule_handle)


class AutomowerMessageEventEntity(AutomowerBaseEntity, EventEntity):
    """Automower EventEntity for error messages."""

    entity_description: EventEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: EventEntityDescription,
    ) -> None:
        """Initialize the Automower error event."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"
        self.mower_id = mower_id

    @callback
    def async_handle_new_message(self, msg_data: SingleMessageData) -> None:
        """Handle new message from API."""
        if msg_data.id != self.mower_id:
            return
        message: Message = msg_data.attributes.message
        code = message.code
        if not code:
            return

        self._trigger_event(
            code,
            {
                ATTR_SEVERITY: message.severity,
                ATTR_LATITUDE: message.latitude,
                ATTR_LONGITUDE: message.longitude,
            },
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for message updates."""
        await super().async_added_to_hass()
        self.coordinator.api.register_single_message_callback(
            self.async_handle_new_message
        )
