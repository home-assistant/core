"""Creates the sensor entities for the mower."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from aioautomower.model import MessageData

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AutomowerConfigEntry
from .const import ERROR_KEYS
from .coordinator import AutomowerMessageUpdateCoordinator
from .entity import AutomowerMessageBaseEntity

_LOGGER = logging.getLogger(__name__)
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

ATTR_WORK_AREA_ID_ASSIGNMENT = "work_area_id_assignment"


@dataclass(frozen=True, kw_only=True)
class AutomowerMessageEventEntityDescription(EventEntityDescription):
    """Describes Automower sensor entity."""

    exists_fn: Callable[[MessageData], bool] = lambda _: True
    option_fn: Callable[[MessageData], list[str] | None] = lambda _: None
    value_fn: Callable[[MessageData], StateType | datetime]


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
    """Set up sensor platform."""
    message_coordinator = entry.runtime_data.message_coordinators
    entities: list[EventEntity] = []
    for mower_id in message_coordinator:
        entities.extend(
            AutomowerMessageEventEntity(
                mower_id,
                message_coordinator[mower_id],
                description,
            )
            for description in MESSAGE_SENSOR_TYPES
            if description.exists_fn(message_coordinator[mower_id].data)
        )
    async_add_entities(entities)


class AutomowerMessageEventEntity(AutomowerMessageBaseEntity, EventEntity):
    """Defining the Automower Sensors with AutomowerSensorEntityDescription."""

    entity_description: AutomowerMessageEventEntityDescription
    _attr_event_types = ERROR_KEYS

    def __init__(
        self,
        mower_id: str,
        message_coordinator: AutomowerMessageUpdateCoordinator,
        description: AutomowerMessageEventEntityDescription,
    ) -> None:
        """Set up AutomowerSensors."""
        super().__init__(mower_id, message_coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"
        self.message_coordinator = message_coordinator

    @callback
    def _async_handle_event(self) -> None:
        """Handle the demo button event."""
        last_message = self.message_coordinator.data.attributes.messages[0]
        if last_message.code:
            self._trigger_event(
                last_message.code,
                {
                    "severity": last_message.severity,
                    "latitude": last_message.latitude,
                    "longitude": last_message.longitude,
                },
            )
            # self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        self._async_handle_event()
        return super()._handle_coordinator_update()
