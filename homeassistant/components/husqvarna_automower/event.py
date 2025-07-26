"""Creates the sensor entities for the mower."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging

from aioautomower.exceptions import ApiError
from aioautomower.model import Message, MessageData

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
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


@dataclass(frozen=True, kw_only=True)
class AutomowerMessageEventEntityDescription(EventEntityDescription):
    """Describes an Automower message event."""

    exists_fn: Callable[[MessageData], bool] = lambda _: True
    value_fn: Callable[[MessageData], str | None]


MESSAGE_SENSOR_TYPES: tuple[AutomowerMessageEventEntityDescription, ...] = (
    AutomowerMessageEventEntityDescription(
        key="last_error",
        translation_key="last_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda data: bool(data.attributes.messages),
        value_fn=lambda data: (
            data.attributes.messages[0].code if data.attributes.messages else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Automower message event entities."""
    coordinator: AutomowerDataUpdateCoordinator = entry.runtime_data

    async def _async_add_message_entities(mower_ids: set[str]) -> None:
        """Fetch messages per mower and add EventEntities for those with data."""

        async def _fetch(mower_id: str) -> MessageData | None:
            """Try to get MessageData for one mower, log and skip exceptions."""
            try:
                msg_data = await coordinator.api.async_get_messages(mower_id)
            except ApiError as err:
                _LOGGER.debug("Error fetching messages for %s: %s", mower_id, err)
                return None
            return msg_data

        tasks = [_fetch(mower_id) for mower_id in mower_ids]
        results = await asyncio.gather(*tasks)

        valid_msgs = [msg for msg in results if isinstance(msg, MessageData)]

        async_add_entities(
            AutomowerMessageEventEntity(msg.id, coordinator, description)
            for msg in valid_msgs
            for description in MESSAGE_SENSOR_TYPES
            if description.exists_fn(msg)
        )

    await _async_add_message_entities(set(coordinator.data))

    coordinator.new_devices_callbacks.append(
        lambda mower_ids: hass.create_task(_async_add_message_entities(mower_ids))
    )


class AutomowerMessageEventEntity(AutomowerBaseEntity, EventEntity):
    """Automower EventEntity for error messages."""

    entity_description: AutomowerMessageEventEntityDescription
    _attr_event_types = ERROR_KEYS

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerMessageEventEntityDescription,
    ) -> None:
        """Initialize the Automower error event."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"
        self.coordinator = coordinator
        self.mower_id = mower_id

    @callback
    def async_handle_new_message(self, msg_data: MessageData) -> None:
        """Handle new message from API."""
        message: Message = msg_data.attributes.messages[0]
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
        self.coordinator.api.register_message_callback(
            self.async_handle_new_message, self.mower_id
        )
