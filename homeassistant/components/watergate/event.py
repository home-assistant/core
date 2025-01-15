"""Module contains the AutoShutOffEvent class for handling auto shut off events."""

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import WatergateConfigEntry
from .const import AUTO_SHUT_OFF_EVENT_NAME
from .coordinator import WatergateDataCoordinator
from .entity import WatergateEntity

VOLUME_AUTO_SHUT_OFF = "volume_threshold"
DURATION_AUTO_SHUT_OFF = "duration_threshold"

DESCRIPTIONS: list[EventEntityDescription] = [
    EventEntityDescription(translation_key="auto_shut_off", key="auto_shut_off")
]

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Event entities from config entry."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        AutoShutOffEvent(coordinator, description) for description in DESCRIPTIONS
    )


class AutoShutOffEvent(WatergateEntity, EventEntity):
    """Event for Auto Shut Off."""

    entity_description: EventEntityDescription

    _attr_event_types = [VOLUME_AUTO_SHUT_OFF, DURATION_AUTO_SHUT_OFF]

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
        entity_description: EventEntityDescription,
    ) -> None:
        """Initialize Auto Shut Off Entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    async def async_added_to_hass(self):
        """Register the callback for event handling when the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(
                AUTO_SHUT_OFF_EVENT_NAME, self._async_handle_event
            )
        )

    @callback
    def _async_handle_event(self, event: Event[dict[str, StateType]]) -> None:
        self._trigger_event(
            str(event.data["type"]).lower(),
            {"volume": event.data["volume"], "duration": event.data["duration"]},
        )
        self.async_write_ha_state()
