"""Event platform for Google Nest."""

from dataclasses import dataclass
import logging

from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.event import EventMessage, EventType
from google_nest_sdm.traits import TraitType

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_DEVICE_MANAGER, DOMAIN
from .device_info import NestDeviceInfo
from .events import (
    EVENT_CAMERA_MOTION,
    EVENT_CAMERA_PERSON,
    EVENT_CAMERA_SOUND,
    EVENT_DOORBELL_CHIME,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class NestEventEntityDescription(EventEntityDescription):
    """Entity description for nest event entities."""

    trait_type: TraitType | None = None
    api_event_type: EventType | None = None
    event_type: str | None = None
    has_entity_name = True


ENTITY_DESCRIPTIONS = [
    NestEventEntityDescription(
        key=EVENT_DOORBELL_CHIME,
        name="Chime",
        device_class=EventDeviceClass.DOORBELL,
        trait_type=TraitType.DOORBELL_CHIME,
        api_event_type=EventType.DOORBELL_CHIME,
    ),
    NestEventEntityDescription(
        key=EVENT_CAMERA_MOTION,
        name="Motion",
        device_class=EventDeviceClass.MOTION,
        trait_type=TraitType.CAMERA_MOTION,
        api_event_type=EventType.CAMERA_MOTION,
    ),
    NestEventEntityDescription(
        key=EVENT_CAMERA_PERSON,
        name="Person",
        device_class=EventDeviceClass.MOTION,
        trait_type=TraitType.CAMERA_PERSON,
        api_event_type=EventType.CAMERA_PERSON,
    ),
    NestEventEntityDescription(
        key=EVENT_CAMERA_SOUND,
        name="Sound",
        device_class=EventDeviceClass.MOTION,
        trait_type=TraitType.CAMERA_SOUND,
        api_event_type=EventType.CAMERA_SOUND,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    device_manager: DeviceManager = hass.data[DOMAIN][entry.entry_id][
        DATA_DEVICE_MANAGER
    ]
    async_add_entities(
        NestTraitEventEntity(entity_description, device)
        for device in device_manager.devices.values()
        for entity_description in ENTITY_DESCRIPTIONS
        if entity_description.trait_type in device.traits
    )


class NestTraitEventEntity(EventEntity):
    """Nest doorbell event entity."""

    entity_description: NestEventEntityDescription
    _attr_should_poll = False

    def __init__(
        self, entity_description: NestEventEntityDescription, device: Device
    ) -> None:
        """Initialize the event entity."""
        self.entity_description = entity_description
        self._device = device
        self._attr_unique_id = f"{device.name}-{entity_description.key}"
        self._attr_device_info = NestDeviceInfo(device).device_info
        self._attr_event_types = [entity_description.key]

    async def _async_handle_event(self, event_message: EventMessage) -> None:
        """Handle a device event."""
        if (
            event_message.relation_update
            or not event_message.resource_update_name
            or not (events := event_message.resource_update_events)
        ):
            return
        for api_event_type, nest_event in events.items():
            if self.entity_description.api_event_type != api_event_type:
                continue

            self._trigger_event(
                self.entity_description.key,
                {"nest_event_id": nest_event.event_token},
            )
            self.async_write_ha_state()
            return

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to attach an event listener."""
        self.async_on_remove(self._device.add_event_callback(self._async_handle_event))
