"""Demo platform that offers a fake siren device."""
from typing import List, Optional

from homeassistant.components.siren import SirenEntity
from homeassistant.components.siren.const import SUPPORT_TONES, SUPPORT_VOLUME_SET

SUPPORT_FLAGS = 0


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Demo siren devices."""
    async_add_entities(
        [
            DemoSiren(name="Siren"),
            DemoSiren(
                name="Siren with all features",
                active_tone="fire",
                available_tones=["fire", "alarm"],
                volume_level=0.5,
            ),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo siren devices config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoSiren(SirenEntity):
    """Representation of a demo siren device."""

    def __init__(
        self,
        name: str,
        active_tone: str | None = None,
        available_tones: str | None = None,
        volume_level: float = None,
        is_on: bool = True,
    ) -> None:
        """Initialize the siren device."""
        self._name = name
        self._state = is_on
        self._support_flags = SUPPORT_FLAGS
        if active_tone is not None and available_tones is not None:
            self._support_flags = self._support_flags | SUPPORT_TONES
        self._active_tone = active_tone
        self._available_tones = available_tones
        if volume_level is not None:
            self._support_flags = self._support_flags | SUPPORT_VOLUME_SET
        self._volume_level = volume_level

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._support_flags

    @property
    def should_poll(self) -> bool:
        """Return the polling state."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the siren device."""
        return self._name

    @property
    def active_tone(self) -> Optional[str]:
        """Return the active tone."""
        return self._active_tone

    @property
    def available_tones(self) -> Optional[List[str]]:
        """Return the available tones."""
        return self._available_tones

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._volume_level

    @property
    def is_on(self) -> bool:
        """Return true if the siren is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the siren on."""
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the siren off."""
        self._state = False
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume_level: float) -> None:
        """Set new volume level."""
        self._volume_level = volume_level
        self.async_write_ha_state()

    async def async_set_active_tone(self, tone: str) -> None:
        """Update active tone."""
        self._active_tone = tone
        self.async_write_ha_state()
