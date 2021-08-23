"""Support for Amcrest IP camera binary sensors."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import logging

from amcrest import AmcrestError
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SOUND,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_BINARY_SENSORS, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import Throttle

from .const import (
    BINARY_SENSOR_SCAN_INTERVAL_SECS,
    DATA_AMCREST,
    DEVICES,
    SERVICE_EVENT,
    SERVICE_UPDATE,
)
from .helpers import log_update_error, service_signal


@dataclass
class AmcrestSensorEntityDescription(BinarySensorEntityDescription):
    """Describe Amcrest sensor entity."""

    event_code: str | None = None


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=BINARY_SENSOR_SCAN_INTERVAL_SECS)
_ONLINE_SCAN_INTERVAL = timedelta(seconds=60 - BINARY_SENSOR_SCAN_INTERVAL_SECS)

BINARY_SENSOR_AUDIO_DETECTED = "audio_detected"
BINARY_SENSOR_AUDIO_DETECTED_POLLED = "audio_detected_polled"
BINARY_SENSOR_MOTION_DETECTED = "motion_detected"
BINARY_SENSOR_MOTION_DETECTED_POLLED = "motion_detected_polled"
BINARY_SENSOR_ONLINE = "online"
BINARY_SENSOR_CROSSLINE_DETECTED = "crossline_detected"
BINARY_SENSOR_CROSSLINE_DETECTED_POLLED = "crossline_detected_polled"
BINARY_POLLED_SENSORS = [
    BINARY_SENSOR_AUDIO_DETECTED_POLLED,
    BINARY_SENSOR_MOTION_DETECTED_POLLED,
    BINARY_SENSOR_ONLINE,
]
_AUDIO_DETECTED_PARAMS = ("Audio Detected", DEVICE_CLASS_SOUND, "AudioMutation")
_MOTION_DETECTED_PARAMS = ("Motion Detected", DEVICE_CLASS_MOTION, "VideoMotion")
_CROSSLINE_DETECTED_PARAMS = (
    "CrossLine Detected",
    DEVICE_CLASS_MOTION,
    "CrossLineDetection",
)
RAW_BINARY_SENSORS = {
    BINARY_SENSOR_AUDIO_DETECTED: _AUDIO_DETECTED_PARAMS,
    BINARY_SENSOR_AUDIO_DETECTED_POLLED: _AUDIO_DETECTED_PARAMS,
    BINARY_SENSOR_MOTION_DETECTED: _MOTION_DETECTED_PARAMS,
    BINARY_SENSOR_MOTION_DETECTED_POLLED: _MOTION_DETECTED_PARAMS,
    BINARY_SENSOR_CROSSLINE_DETECTED: _CROSSLINE_DETECTED_PARAMS,
    BINARY_SENSOR_CROSSLINE_DETECTED_POLLED: _CROSSLINE_DETECTED_PARAMS,
    BINARY_SENSOR_ONLINE: ("Online", DEVICE_CLASS_CONNECTIVITY, None),
}
BINARY_SENSORS: tuple[AmcrestSensorEntityDescription, ...] = tuple(
    AmcrestSensorEntityDescription(
        key=key,
        device_class=device_class,
        name=name,
        event_code=event_code,
    )
    for key, (name, device_class, event_code) in RAW_BINARY_SENSORS.items()
)
BINARY_SENSOR_KEYS = [description.key for description in BINARY_SENSORS]
_EXCLUSIVE_OPTIONS = [
    {BINARY_SENSOR_MOTION_DETECTED, BINARY_SENSOR_MOTION_DETECTED_POLLED},
    {BINARY_SENSOR_CROSSLINE_DETECTED, BINARY_SENSOR_CROSSLINE_DETECTED_POLLED},
]

_UPDATE_MSG = "Updating %s binary sensor"


def check_binary_sensors(value):
    """Validate binary sensor configurations."""
    for exclusive_options in _EXCLUSIVE_OPTIONS:
        if len(set(value) & exclusive_options) > 1:
            raise vol.Invalid(
                f"must contain at most one of {', '.join(exclusive_options)}."
            )
    return value


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a binary sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    binary_sensors = discovery_info[CONF_BINARY_SENSORS]
    async_add_entities(
        [
            AmcrestBinarySensor(name, device, entity_description)
            for entity_description in BINARY_SENSORS
            if entity_description.key in binary_sensors
        ],
        True,
    )


class AmcrestBinarySensor(BinarySensorEntity):
    """Binary sensor for Amcrest camera."""

    def __init__(self, name, device, entity_description):
        """Initialize entity."""
        self._signal_name = name
        self._api = device.api
        self.entity_description = entity_description
        self._attr_name = f"{name} {entity_description.name}"
        self._attr_should_poll = entity_description.key in BINARY_POLLED_SENSORS
        self._unsub_dispatcher = []

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            self.entity_description.key == BINARY_SENSOR_ONLINE or self._api.available
        )

    def update(self):
        """Update entity."""
        if self.entity_description.key == BINARY_SENSOR_ONLINE:
            self._update_online()
        else:
            self._update_others()

    @Throttle(_ONLINE_SCAN_INTERVAL)
    def _update_online(self):
        if not (self._api.available or self.is_on):
            return
        _LOGGER.debug(_UPDATE_MSG, self.name)
        if self._api.available:
            # Send a command to the camera to test if we can still communicate with it.
            # Override of Http.command() in __init__.py will set self._api.available
            # accordingly.
            with suppress(AmcrestError):
                self._api.current_time  # pylint: disable=pointless-statement
        self._attr_is_on = self._api.available

    def _update_others(self):
        if not self.available:
            return
        _LOGGER.debug(_UPDATE_MSG, self.name)

        event_code = self.entity_description.event_code
        try:
            self._attr_is_on = "channels" in self._api.event_channels_happened(
                event_code
            )
        except AmcrestError as error:
            log_update_error(_LOGGER, "update", self.name, "binary sensor", error)

    async def async_on_demand_update(self):
        """Update state."""
        if self.entity_description.key == BINARY_SENSOR_ONLINE:
            _LOGGER.debug(_UPDATE_MSG, self.name)
            self._attr_is_on = self._api.available
            self.async_write_ha_state()
            return
        self.async_schedule_update_ha_state(True)

    @callback
    def async_event_received(self, start):
        """Update state from received event."""
        _LOGGER.debug(_UPDATE_MSG, self.name)
        self._attr_is_on = start
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to signals."""
        self._unsub_dispatcher.append(
            async_dispatcher_connect(
                self.hass,
                service_signal(SERVICE_UPDATE, self._signal_name),
                self.async_on_demand_update,
            )
        )
        if (
            self.entity_description.event_code
            and self.entity_description.key not in BINARY_POLLED_SENSORS
        ):
            self._unsub_dispatcher.append(
                async_dispatcher_connect(
                    self.hass,
                    service_signal(
                        SERVICE_EVENT,
                        self._signal_name,
                        self.entity_description.event_code,
                    ),
                    self.async_event_received,
                )
            )

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        for unsub_dispatcher in self._unsub_dispatcher:
            unsub_dispatcher()
