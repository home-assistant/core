"""Support for Hikvision event stream events represented as binary sensors."""

import logging
from typing import Any, override

from pyhik.constants import SENSOR_MAP

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_LAST_TRIP_TIME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .entity import HikvisionEntity

# Keyed by the friendly names pyhik emits in `current_event_states`. Going
# through SENSOR_MAP keeps each description attached to the right event if
# pyhik renames a label.
BINARY_SENSOR_DESCRIPTIONS: dict[str, BinarySensorEntityDescription] = {
    SENSOR_MAP["vmd"]: BinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["linedetection"]: BinarySensorEntityDescription(
        key="line_crossing",
        translation_key="line_crossing",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["fielddetection"]: BinarySensorEntityDescription(
        key="field_detection",
        translation_key="field_detection",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["tamperdetection"]: BinarySensorEntityDescription(
        key="tamper_detection",
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    SENSOR_MAP["diskfull"]: BinarySensorEntityDescription(
        key="disk_full",
        translation_key="disk_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SENSOR_MAP["diskerror"]: BinarySensorEntityDescription(
        key="disk_error",
        translation_key="disk_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SENSOR_MAP["nicbroken"]: BinarySensorEntityDescription(
        key="net_interface_broken",
        translation_key="net_interface_broken",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SENSOR_MAP["ipconflict"]: BinarySensorEntityDescription(
        key="ip_conflict",
        translation_key="ip_conflict",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SENSOR_MAP["illaccess"]: BinarySensorEntityDescription(
        key="illegal_access",
        translation_key="illegal_access",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    SENSOR_MAP["videomismatch"]: BinarySensorEntityDescription(
        key="video_mismatch",
        translation_key="video_mismatch",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SENSOR_MAP["badvideo"]: BinarySensorEntityDescription(
        key="bad_video",
        translation_key="bad_video",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SENSOR_MAP["pir"]: BinarySensorEntityDescription(
        key="pir_alarm",
        translation_key="pir_alarm",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["facedetection"]: BinarySensorEntityDescription(
        key="face_detection",
        translation_key="face_detection",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["scenechangedetection"]: BinarySensorEntityDescription(
        key="scene_change_detection",
        translation_key="scene_change_detection",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["io"]: BinarySensorEntityDescription(
        key="io",
        translation_key="io",
    ),
    SENSOR_MAP["unattendedbaggage"]: BinarySensorEntityDescription(
        key="unattended_baggage",
        translation_key="unattended_baggage",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["attendedbaggage"]: BinarySensorEntityDescription(
        key="attended_baggage",
        translation_key="attended_baggage",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["recordingfailure"]: BinarySensorEntityDescription(
        key="recording_failure",
        translation_key="recording_failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SENSOR_MAP["regionexiting"]: BinarySensorEntityDescription(
        key="exiting_region",
        translation_key="exiting_region",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["regionentrance"]: BinarySensorEntityDescription(
        key="entering_region",
        translation_key="entering_region",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    SENSOR_MAP["thermometry"]: BinarySensorEntityDescription(
        key="temperature_alarm",
        translation_key="temperature_alarm",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
}

# pyhik uses videoloss as a connection watchdog and does not parse duration
# (ongoing events) packets, so neither is a user-facing event: a leaked entry
# gets no entity and no unknown-sensor warning.
IGNORED_SENSOR_TYPES: frozenset[str] = frozenset(
    {SENSOR_MAP["videoloss"], SENSOR_MAP["duration"]}
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hikvision binary sensors from a config entry."""
    data = entry.runtime_data
    camera = data.camera

    sensors = camera.current_event_states
    if sensors is None or not sensors:
        _LOGGER.warning(
            "Hikvision %s %s has no sensors available. "
            "Ensure event detection is enabled and configured on the device",
            data.device_type,
            data.device_name,
        )
        return

    for sensor_type in sensors:
        if (
            sensor_type not in BINARY_SENSOR_DESCRIPTIONS
            and sensor_type not in IGNORED_SENSOR_TYPES
        ):
            _LOGGER.warning(
                "Unknown Hikvision sensor type '%s', please report this at "
                "https://github.com/home-assistant/core/issues",
                sensor_type,
            )

    entities: list[HikvisionBinarySensor] = []
    for sensor_type, channel_list in sensors.items():
        if sensor_type not in BINARY_SENSOR_DESCRIPTIONS:
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
                HikvisionBinarySensor(
                    hass=hass,
                    entry=entry,
                    description=BINARY_SENSOR_DESCRIPTIONS[sensor_type],
                    sensor_type=sensor_type,
                    channel=channel,
                )
            )

    async_add_entities(entities)


class HikvisionBinarySensor(HikvisionEntity, BinarySensorEntity):
    """Representation of a Hikvision binary sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HikvisionConfigEntry,
        description: BinarySensorEntityDescription,
        sensor_type: str,
        channel: int,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(hass, entry, channel)
        self.entity_description = description
        self._sensor_type = sensor_type

        # Build unique ID (includes sensor_type for uniqueness per sensor)
        self._attr_unique_id = f"{self._data.device_id}_{sensor_type}_{channel}"

        # Callback ID for pyhik
        self._callback_id = f"{self._data.device_id}.{sensor_type}.{channel}"

    def _get_sensor_attributes(self) -> tuple[bool, Any, Any, Any]:
        """Get sensor attributes from camera."""
        return self._camera.fetch_attributes(self._sensor_type, self._channel)

    @property
    @override
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self._get_sensor_attributes()[0]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = self._get_sensor_attributes()
        return {ATTR_LAST_TRIP_TIME: attrs[3]}
