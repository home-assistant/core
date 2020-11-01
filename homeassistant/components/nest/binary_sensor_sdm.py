"""Support for Google Nest SDM binary_sensors."""

import datetime
import logging
from typing import Optional

from google_nest_sdm.camera_traits import (
    CameraMotionTrait,
    CameraPersonTrait,
    CameraSoundTrait,
)
from google_nest_sdm.device import Device
from google_nest_sdm.doorbell_traits import DoorbellChimeTrait
from google_nest_sdm.event import (
    CameraMotionEvent,
    CameraPersonEvent,
    CameraSoundEvent,
    DoorbellChimeEvent,
    EventCallback,
    EventMessage,
    EventTypeFilterCallback,
    RecentEventFilterCallback,
)

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_SOUND,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .device_info import DeviceInfo

_LOGGER = logging.getLogger(__name__)


# Amount of time that an event is "on" when receiving a pubsub message
EVENT_DURATION_SECS = 30

# Drop any pubsub messages older than 1 minute old so that we don't
# bother firing events for super old messages on startup.
OLDEST_MESSAGE_AGE = datetime.timedelta(seconds=60)


class BinarySensorEventConfig:
    """Holds entity name, traits, and supported events."""

    def __init__(self, label, trait_name, event_name, device_class):
        """Initialize the BinarySensorEventConfig."""
        self.label = label
        self.trait_name = trait_name
        self.event_name = event_name
        self.device_class = device_class


BINARY_SENSOR_EVENT_CONFIG = [
    BinarySensorEventConfig(
        "Doorbell Chime",
        DoorbellChimeTrait.NAME,
        DoorbellChimeEvent.NAME,
        DEVICE_CLASS_OCCUPANCY,
    ),
    BinarySensorEventConfig(
        "Camera Motion",
        CameraMotionTrait.NAME,
        CameraMotionEvent.NAME,
        DEVICE_CLASS_MOTION,
    ),
    BinarySensorEventConfig(
        "Camera Person",
        CameraPersonTrait.NAME,
        CameraPersonEvent.NAME,
        DEVICE_CLASS_MOTION,
    ),
    BinarySensorEventConfig(
        "Camera Sound", CameraSoundTrait.NAME, CameraSoundEvent.NAME, DEVICE_CLASS_SOUND
    ),
]


async def async_setup_sdm_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the binary_sensors."""

    subscriber = hass.data[DOMAIN][entry.entry_id]
    device_manager = await subscriber.async_get_device_manager()

    entities = []
    for device in device_manager.devices.values():
        # Create a binary sensor for each event type supported by the device.
        for config in BINARY_SENSOR_EVENT_CONFIG:
            if config.trait_name in device.traits:
                entities.append(EventBinarySensor(device, config))
    async_add_entities(entities)


class EventBinarySensor(BinarySensorEntity, EventCallback):
    """Representation of a binary sensory that turns on for events."""

    def __init__(self, device: Device, config: BinarySensorEventConfig):
        """Initialize the binary sensor."""
        self._device = device
        self._device_info = DeviceInfo(device)
        self._config = config
        self._event_expires_at = None
        self._handle_event_unsub = None
        self._handle_off_unsub = None

    @property
    def should_poll(self) -> bool:
        """Disable polling since entities have state pushed via pubsub."""
        return False

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        # The API "name" field is a unique device identifier.
        return f"{self._device.name}-{self._config.trait_name}"

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"{self._device_info.device_name} {self._config.label}"

    @property
    def device_info(self):
        """Return device specific attributes."""
        return self._device_info.device_info

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._event_expires_at is not None and utcnow() < self._event_expires_at

    async def async_added_to_hass(self):
        """Run when entity is added to register update callback."""
        # Register to be notified about events only of the relevant type for
        # this binary sensor.
        self._handle_event_unsub = self._device.add_event_callback(
            RecentEventFilterCallback(
                OLDEST_MESSAGE_AGE,
                EventTypeFilterCallback(
                    self._config.event_name,  # Only match certain events
                    self,  # Invoke self.handle_event as callback
                ),
            )
        )

    async def async_will_remove_from_hass(self):
        """Run when the entity is getting removed to unregister callback."""
        if self._handle_event_unsub:
            _LOGGER.debug("Unregistering from device updates")
            self._handle_event_unsub()
        if self._handle_off_unsub:
            _LOGGER.debug("Unregistering from event callbacks")
            self._handle_off_unsub()

    def handle_event(self, event_message: EventMessage):
        """Process a message, running in the background pubsub thread."""
        self.hass.async_create_task(self.handle_on_event())

    async def handle_on_event(self):
        """Turn on the sensor and schedules an off event."""
        self._event_expires_at = (
            utcnow()
            + datetime.timedelta(seconds=EVENT_DURATION_SECS)
            # Fudge factor to ensure handle_off_event is called well past expiration
            - datetime.timedelta(milliseconds=100)
        )

        _LOGGER.debug("on until %s", self._event_expires_at)
        self.async_write_ha_state()
        self._handle_off_unsub = async_call_later(
            self.hass, EVENT_DURATION_SECS, self.handle_off_event
        )

    async def handle_off_event(self, now):
        """Turn off the sensor."""
        if not self._event_expires_at:
            return
        if now < self._event_expires_at:
            # Another message may have been received which updated the
            # expiration time.  Let that events alarm do the cleanup
            return
        _LOGGER.debug("event expired")
        self._event_expires_at = None
        self.async_write_ha_state()

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._config.device_class
