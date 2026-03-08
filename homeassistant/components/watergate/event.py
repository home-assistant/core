"""Module contains the AutoShutOffEvent class for handling auto shut off events."""

from watergate_local_api.models.auto_shut_off_report import AutoShutOffReport

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WatergateConfigEntry
from .const import AUTO_SHUT_OFF_EVENT_NAME
from .coordinator import WatergateDataCoordinator
from .entity import WatergateEntity

VOLUME_AUTO_SHUT_OFF = "volume_threshold"
DURATION_AUTO_SHUT_OFF = "duration_threshold"


DESCRIPTIONS: list[EventEntityDescription] = [
    EventEntityDescription(
        translation_key="auto_shut_off_volume",
        key="auto_shut_off_volume",
        event_types=[VOLUME_AUTO_SHUT_OFF],
    ),
    EventEntityDescription(
        translation_key="auto_shut_off_duration",
        key="auto_shut_off_duration",
        event_types=[DURATION_AUTO_SHUT_OFF],
    ),
]

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Event entities from config entry."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        AutoShutOffEvent(coordinator, description) for description in DESCRIPTIONS
    )


class AutoShutOffEvent(WatergateEntity, EventEntity):
    """Event for Auto Shut Off."""

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
            async_dispatcher_connect(
                self.hass,
                AUTO_SHUT_OFF_EVENT_NAME.format(self.event_types[0]),
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event: AutoShutOffReport) -> None:
        self._trigger_event(
            event.type.lower(),
            {"volume": event.volume, "duration": event.duration},
        )
        self.async_write_ha_state()
