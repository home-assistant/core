"""Support for Hikvision smart events represented as event entities."""

import logging
from typing import Any, override

from pyhik.constants import SENSOR_MAP

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .entity import HikvisionEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Smart events classify what tripped them. Firmware that does not classify, and
# every trip of a non-smart event, reports no target at all.
DETECTION_TARGETS = ("human", "pet", "vehicle")
EVENT_TYPE_TRIGGERED = "triggered"
EVENT_TYPES = [EVENT_TYPE_TRIGGERED, *DETECTION_TARGETS]

# Keyed by the friendly names pyhik emits in `current_event_states`, like the
# binary sensor descriptions, so both platforms name the same event the same
# way. Only the events that can carry a detection target are listed; the rest
# are already fully described by their binary sensor.
EVENT_DESCRIPTIONS: dict[str, EventEntityDescription] = {
    SENSOR_MAP["vmd"]: EventEntityDescription(
        key="motion",
        translation_key="motion",
        device_class=EventDeviceClass.MOTION,
        event_types=EVENT_TYPES,
    ),
    SENSOR_MAP["linedetection"]: EventEntityDescription(
        key="line_crossing",
        translation_key="line_crossing",
        device_class=EventDeviceClass.MOTION,
        event_types=EVENT_TYPES,
    ),
    SENSOR_MAP["fielddetection"]: EventEntityDescription(
        key="field_detection",
        translation_key="field_detection",
        device_class=EventDeviceClass.MOTION,
        event_types=EVENT_TYPES,
    ),
}


def event_type_for_target(detection_target: str | None) -> str:
    """Return the event type for a pyhik detection target."""
    if detection_target is None:
        return EVENT_TYPE_TRIGGERED
    if detection_target not in DETECTION_TARGETS:
        _LOGGER.warning(
            "Unknown Hikvision detection target '%s', please report this at "
            "https://github.com/home-assistant/core/issues",
            detection_target,
        )
        return EVENT_TYPE_TRIGGERED
    return detection_target


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hikvision events from a config entry."""
    sensors = entry.runtime_data.camera.current_event_states
    if not sensors:
        return

    entities: list[HikvisionEvent] = []
    for sensor_type, channel_list in sensors.items():
        description = EVENT_DESCRIPTIONS.get(sensor_type)
        if description is None:
            continue
        # pyhik can report the same channel more than once for a sensor type
        # (e.g. when a channel has several notification methods enabled), so
        # deduplicate on the channel to avoid colliding unique IDs.
        seen_channels: set[int] = set()
        for channel_info in channel_list:
            channel = channel_info[1]
            if channel in seen_channels:
                continue
            seen_channels.add(channel)
            entities.append(
                HikvisionEvent(
                    hass=hass,
                    entry=entry,
                    description=description,
                    sensor_type=sensor_type,
                    channel=channel,
                )
            )

    async_add_entities(entities)


class HikvisionEvent(HikvisionEntity, EventEntity):
    """Representation of a Hikvision event."""

    _attr_should_poll = False
    entity_description: EventEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HikvisionConfigEntry,
        description: EventEntityDescription,
        sensor_type: str,
        channel: int,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(hass, entry, channel)
        self.entity_description = description
        self._sensor_type = sensor_type

        self._attr_unique_id = f"{self._data.device_id}_{sensor_type}_{channel}"

        # pyhik routes an update to the callbacks registered under this exact
        # identifier and passes it back as the callback's message.
        self._callback_id = f"{self._data.device_id}.{sensor_type}.{channel}"

        # An event already active at startup must not be replayed as new.
        self._is_on = self._get_sensor_attributes()[0]

    def _get_sensor_attributes(self) -> tuple[bool, Any, Any, Any, str | None]:
        """Get sensor attributes from camera."""
        return self._camera.fetch_attributes(self._sensor_type, self._channel)

    @property
    @override
    def available(self) -> bool:
        """Return true if the device's event stream is connected."""
        return self._camera.stream_connected

    @override
    async def async_added_to_hass(self) -> None:
        """Register callback when entity is added."""
        await super().async_added_to_hass()

        self._camera.add_update_callback(self._update_callback, self._callback_id)

    def _update_callback(self, msg: str) -> None:
        """Handle an update from pyhik's event stream thread."""
        # Read the state on the callback thread: a trip that has already ended
        # by the time the event loop runs would otherwise be read as inactive
        # by both handlers and never fire.
        self.hass.loop.call_soon_threadsafe(
            self._async_handle_update, self._get_sensor_attributes()
        )

    @callback
    def _async_handle_update(
        self, attributes: tuple[bool, Any, Any, Any, str | None]
    ) -> None:
        """Trigger an event when the underlying event has turned on."""
        is_on = attributes[0]
        if is_on and not self._is_on:
            self._trigger_event(event_type_for_target(attributes[4]))
        self._is_on = is_on
        self.async_write_ha_state()
