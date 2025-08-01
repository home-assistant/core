"""Creates the event entities for supported mowers."""

from collections.abc import Callable
import logging

from aioautomower.model import SingleMessageData

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutomowerConfigEntry
from .const import ERROR_KEYS
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

ATTR_SEVERITY = "severity"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"
ATTR_DATE_TIME = "date_time"


EVENT_DESCRIPTIONS = [
    EventEntityDescription(
        key="message",
        translation_key="message",
        event_types=ERROR_KEYS,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Automower message event entities.

    Not all mowers support message events, so we create entities
    only for those that do. The entities are created dynamically
    based on the messages received from the API.
    """
    coordinator: AutomowerDataUpdateCoordinator = config_entry.runtime_data

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)

    seen_mowers = {}
    for entry in entries:
        if entry.unique_id.endswith("_message"):
            mower_id = entry.unique_id.removesuffix("_message")
            seen_mowers[mower_id] = True

    def _add_for_mower(mower_id: str) -> None:
        seen_mowers[mower_id] = True
        entities = [
            AutomowerMessageEventEntity(mower_id, coordinator, desc)
            for desc in EVENT_DESCRIPTIONS
        ]
        async_add_entities(entities)

    # Restore and clean up seen mowers
    for mower_id in list(seen_mowers):
        if mower_id in coordinator.data:
            _add_for_mower(mower_id)

    @callback
    def _on_single_message(msg: SingleMessageData) -> None:
        if msg.id not in seen_mowers:
            _add_for_mower(msg.id)

    coordinator.api.register_single_message_callback(_on_single_message)


class AutomowerMessageEventEntity(AutomowerBaseEntity, EventEntity):
    """EventEntity for Automower message events."""

    entity_description: EventEntityDescription
    _message_cb: Callable[[SingleMessageData], None] | None = None

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: EventEntityDescription,
    ) -> None:
        """Initialize Automower message event entity."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"
        self.mower_id = mower_id
        self._message_cb = None

    async def async_added_to_hass(self) -> None:
        """Register callback when entity is added to hass."""
        await super().async_added_to_hass()

        @callback
        def _handle(msg: SingleMessageData) -> None:
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

        self._message_cb = _handle
        self.coordinator.api.register_single_message_callback(self._message_cb)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister WebSocket callback when entity is removed."""
        if self._message_cb:
            self.coordinator.api.unregister_single_message_callback(self._message_cb)
            self._message_cb = None
