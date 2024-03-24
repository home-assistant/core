"""Component providing HA Siren support for Ring Chimes."""

import logging
from typing import Any

from ring_doorbell import RingGeneric
from ring_doorbell.const import CHIME_TEST_SOUND_KINDS, KIND_DING

from homeassistant.components.siren import ATTR_TONE, SirenEntity, SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RING_DEVICES, RING_DEVICES_COORDINATOR
from .coordinator import RingDataCoordinator
from .entity import RingEntity, exception_wrap

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sirens for the Ring devices."""
    devices = hass.data[DOMAIN][config_entry.entry_id][RING_DEVICES]
    coordinator: RingDataCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        RING_DEVICES_COORDINATOR
    ]

    async_add_entities(
        RingChimeSiren(device, coordinator) for device in devices["chimes"]
    )


class RingChimeSiren(RingEntity, SirenEntity):
    """Creates a siren to play the test chimes of a Chime device."""

    _attr_available_tones = CHIME_TEST_SOUND_KINDS
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TONES
    _attr_translation_key = "siren"

    def __init__(self, device: RingGeneric, coordinator: RingDataCoordinator) -> None:
        """Initialize a Ring Chime siren."""
        super().__init__(device, coordinator)
        # Entity class attributes
        self._attr_unique_id = f"{self._device.id}-siren"

    @exception_wrap
    def turn_on(self, **kwargs: Any) -> None:
        """Play the test sound on a Ring Chime device."""
        tone = kwargs.get(ATTR_TONE) or KIND_DING

        self._device.test_sound(kind=tone)
