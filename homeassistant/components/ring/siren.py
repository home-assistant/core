"""Component providing HA Siren support for Ring Chimes."""

import logging
from typing import Any

from ring_doorbell import RingChime, RingEventKind

from homeassistant.components.siren import ATTR_TONE, SirenEntity, SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RingData
from .const import DOMAIN
from .coordinator import RingDataCoordinator
from .entity import RingEntity, exception_wrap

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sirens for the Ring devices."""
    ring_data: RingData = hass.data[DOMAIN][config_entry.entry_id]
    devices_coordinator = ring_data.devices_coordinator

    async_add_entities(
        RingChimeSiren(device, devices_coordinator)
        for device in ring_data.devices.chimes
    )


class RingChimeSiren(RingEntity[RingChime], SirenEntity):
    """Creates a siren to play the test chimes of a Chime device."""

    _attr_available_tones = [RingEventKind.DING.value, RingEventKind.MOTION.value]
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TONES
    _attr_translation_key = "siren"

    def __init__(self, device: RingChime, coordinator: RingDataCoordinator) -> None:
        """Initialize a Ring Chime siren."""
        super().__init__(device, coordinator)
        # Entity class attributes
        self._attr_unique_id = f"{self._device.id}-siren"

    @exception_wrap
    def turn_on(self, **kwargs: Any) -> None:
        """Play the test sound on a Ring Chime device."""
        tone = kwargs.get(ATTR_TONE) or RingEventKind.DING.value

        self._device.test_sound(kind=tone)
