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
    EVENT_NAME_MAP,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class NestEventEntityDescription(EventEntityDescription):
    """Entity description for nest event entities."""

    trait_types: list[TraitType]
    api_event_types: list[EventType]
    event_types: list[str]


ENTITY_DESCRIPTIONS = [
    NestEventEntityDescription(
        key=EVENT_DOORBELL_CHIME,
        translation_key="chime",
        device_class=EventDeviceClass.DOORBELL,
        event_types=[EVENT_DOORBELL_CHIME],
        trait_types=[TraitType.DOORBELL_CHIME],
        api_event_types=[EventType.DOORBELL_CHIME],
    ),
    NestEventEntityDescription(
        key=EVENT_CAMERA_MOTION,
        translation_key="motion",
        device_class=EventDeviceClass.MOTION,
        event_types=[EVENT_CAMERA_MOTION, EVENT_CAMERA_PERSON, EVENT_CAMERA_SOUND],
        trait_types=[
            TraitType.CAMERA_MOTION,
            TraitType.CAMERA_PERSON,
            TraitType.CAMERA_SOUND,
        ],
        api_event_types=[
            EventType.CAMERA_MOTION,
            EventType.CAMERA_PERSON,
            EventType.CAMERA_SOUND,
        ],
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
        NestTraitEventEntity(desc, device)
        for device in device_manager.devices.values()
        for desc in ENTITY_DESCRIPTIONS
        if any(trait in device.traits for trait in desc.trait_types)
    )


class NestTraitEventEntity(EventEntity):
    """Nest doorbell event entity."""

    entity_description: NestEventEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, entity_description: NestEventEntityDescription, device: Device
    ) -> None:
        """Initialize the event entity."""
        self.entity_description = entity_description
        self._device = device
        self._attr_unique_id = f"{device.name}-{entity_description.key}"
        self._attr_device_info = NestDeviceInfo(device).device_info

    async def _async_handle_event(self, event_message: EventMessage) -> None:
        """Handle a device event."""
        if (
            event_message.relation_update
            or not event_message.resource_update_name
            or not (events := event_message.resource_update_events)
        ):
            return
        last_nest_event_id = self.state_attributes.get("nest_event_id")
        for api_event_type, nest_event in events.items():
            if api_event_type not in self.entity_description.api_event_types:
                continue

            event_type = EVENT_NAME_MAP[api_event_type]
            nest_event_id = nest_event.event_token
            if last_nest_event_id is not None and last_nest_event_id == nest_event_id:
                # This event is a duplicate message in the same thread
                return

            self._trigger_event(
                event_type,
                {"nest_event_id": nest_event_id},
            )
            self.async_write_ha_state()
            return

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to attach an event listener."""
        self.async_on_remove(self._device.add_event_callback(self._async_handle_event))
