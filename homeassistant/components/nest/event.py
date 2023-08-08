"""Support for Google Nest Events for Cameras."""

import logging

from google_nest_sdm.camera_traits import (
    CameraMotionTrait,
    CameraPersonTrait,
    CameraSoundTrait,
)
from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.doorbell_traits import DoorbellChimeTrait
from google_nest_sdm.event import EventMessage

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_DEVICE_MANAGER, DOMAIN
from .device_info import NestDeviceInfo

_LOGGER = logging.getLogger(__name__)

DOORBELL_EVENT_TRAINTS = (DoorbellChimeTrait.NAME,)
MOTION_EVENT_TRAINTS = (CameraMotionTrait, CameraPersonTrait, CameraSoundTrait)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the cameras."""

    device_manager: DeviceManager = hass.data[DOMAIN][entry.entry_id][
        DATA_DEVICE_MANAGER
    ]
    entities = []
    for device in device_manager.devices.values():
        if any(trait in device.traits for trait in DOORBELL_EVENT_TRAINTS):
            entities.append(DoorbellEvent(device))

    async_add_entities(entities)


class DoorbellEvent(EventEntity):
    """Entity for handling doorbell press events."""

    def __init__(self, device: Device) -> None:
        """Initialize DoorbellEvent."""
        self._device = device
        self._device_info = NestDeviceInfo(device)
        self._attr_has_entity_name = True
        self._attr_translation_key = "doorbell"
        self._attr_unique_id = f"{device.name}-{self.device_class}"
        self._attr_device_info = self._device_info.device_info
        self._attr_device_class = EventDeviceClass.DOORBELL
        self._attr_event_types = ["press"]

    async def _async_handle_event(self, event_message: EventMessage) -> None:
        """Handle a doorbell press event."""
        if not event_message.resource_update_events:
            return
        if DoorbellChimeTrait.EVENT_NAME in event_message.resource_update_events:
            self._trigger_event("press")
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks with your device API/library."""
        self._device.add_event_callback(self._async_handle_event)


# 2023-08-06 23:32:04.565 DEBUG (MainThread) [google_nest_sdm.event] EventMessage raw_data={
# 'eventId': '86539e37-1beb-4d75-83f8-a38612c20fd7', 'timestamp': '2023-08-06T23:32:01.727Z',
# 'resourceUpdate': {
# 'name': 'enterprises/9e664211-78d7-4e70-936c-a01f14179e36/devices/AVPHwEtV3Lm25VPuln9abzjLCJx6fBD-_dK1FWFYVTbvlQKWi8lBuCkapDdT1HmBZb89OR0HK7oaBfSgoPg7rkXMn3x9nA',
# 'events': {
#   'sdm.devices.events.DoorbellChime.Chime': {
#       'eventSessionId': '1632710533', 'eventId': 'n:2'
#   },
#   'sdm.devices.events.CameraClipPreview.ClipPreview': {
#      'eventSessionId': '1632710533',
#      'previewUrl': 'https://nest-camera-frontend.googleapis.com/frontend/encrypted/clippreview/AXG5WmjWL4kdZadtV-PksmouP-2PUTk8jwg0TOJrnB6YR4cXqC2I1Feq5bOdAQsOJ_BjCi0MD0Wv1OAQS1jdAuQhZ7Rio9ufEGpaqju_4ZDO5KzhCO5u-HJbXh7LXNb5dXVKeXGPuUAXDwlY5wc7ufddlN4cEUin5PntscIbVkUXl2YVKt84OnTfTu6ScF4dvzS6zptF9ghGd3rg0gHWGarZtia-WZr-PYFZhlZCJOzb3fe7V0wuZjPTx2TCNI_mA9ItF5GozTH4BnUW6nCpYVMf7yvFgqeScqIRCKcQ0yiCa5gkMcdImQ=='}}},
#  'userId': 'AVPHwEvuuYrColDDTr3e1FU4cTrF8bdIA8O9JmZ4aUq8',
# 'eventThreadId': '21f8e530-c176-4eb5-ab3f-e574d4c224ec',
# 'resourceGroup': ['enterprises/9e664211-78d7-4e70-936c-a01f14179e36/devices/AVPHwEtV3Lm25VPuln9abzjLCJx6fBD-_dK1FWFYVTbvlQKWi8lBuCkapDdT1HmBZb89OR0HK7oaBfSgoPg7rkXMn3x9nA'],
# 'eventThreadState': 'STARTED'
# }

# 2023-08-06 23:32:24.578 DEBUG (MainThread) [google_nest_sdm.event] EventMessage raw_data={
# 'eventId': '86539e37-1beb-4d75-83f8-a38612c20fd7', 'timestamp': '2023-08-06T23:32:01.727Z',
# 'resourceUpdate': {
#   'name': 'enterprises/9e664211-78d7-4e70-936c-a01f14179e36/devices/AVPHwEtV3Lm25VPuln9abzjLCJx6fBD-_dK1FWFYVTbvlQKWi8lBuCkapDdT1HmBZb89OR0HK7oaBfSgoPg7rkXMn3x9nA',
#   'events': {
#     'sdm.devices.events.DoorbellChime.Chime': {
#         'eventSessionId': '1632710533', 'eventId': 'n:2'
#     },
#     'sdm.devices.events.CameraClipPreview.ClipPreview': {
#         'eventSessionId': '1632710533', 'previewUrl': 'https://nest-camera-frontend.googleapis.com/frontend/encrypted/clippreview/AXG5WmjWL4kdZadtV-PksmouP-2PUTk8jwg0TOJrnB6YR4cXqC2I1Feq5bOdAQsOJ_BjCi0MD0Wv1OAQS1jdAuQhZ7Rio9ufEGpaqju_4ZDO5KzhCO5u-HJbXh7LXNb5dXVKeXGPuUAXDwlY5wc7ufddlN4cEUin5PntscIbVkUXl2YVKt84OnTfTu6ScF4dvzS6zptF9ghGd3rg0gHWGarZtia-WZr-PYFZhlZCJOzb3fe7V0wuZjPTx2TCNI_mA9ItF5GozTH4BnUW6nCpYVMf7yvFgqeScqIRCKcQ0yiCa5gkMcdImQ=='}}},
# 'userId': 'AVPHwEvuuYrColDDTr3e1FU4cTrF8bdIA8O9JmZ4aUq8',
# 'eventThreadId': '21f8e530-c176-4eb5-ab3f-e574d4c224ec',
# 'resourceGroup': ['enterprises/9e664211-78d7-4e70-936c-a01f14179e36/devices/AVPHwEtV3Lm25VPuln9abzjLCJx6fBD-_dK1FWFYVTbvlQKWi8lBuCkapDdT1HmBZb89OR0HK7oaBfSgoPg7rkXMn3x9nA'],
# 'eventThreadState': 'ENDED'
# }
