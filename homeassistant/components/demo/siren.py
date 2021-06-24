"""Demo platform that offers a fake siren device."""
from __future__ import annotations

from typing import Any

from homeassistant.components.siren import SirenEntity
from homeassistant.components.siren.const import SUPPORT_TONES, SUPPORT_VOLUME_SET
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

SUPPORT_FLAGS = 0


async def async_setup_platform(
    hass: HomeAssistant,
    config: Config,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the Demo siren devices."""
    async_add_entities(
        [
            DemoSiren(name="Siren"),
            DemoSiren(
                name="Siren with all features",
                default_tone="fire",
                available_tones=["fire", "alarm"],
                volume_level=0.5,
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo siren devices config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoSiren(SirenEntity):
    """Representation of a demo siren device."""

    def __init__(
        self,
        name: str,
        default_tone: str | None = None,
        available_tones: str | None = None,
        volume_level: float | None = None,
        is_on: bool = True,
    ) -> None:
        """Initialize the siren device."""
        self._attr_name = name
        self._attr_should_poll = False
        self._attr_supported_features = SUPPORT_FLAGS
        self._attr_is_on = is_on
        if default_tone is not None and available_tones is not None:
            self._attr_supported_features = (
                self._attr_supported_features | SUPPORT_TONES
            )
        if volume_level is not None:
            self._attr_supported_features = (
                self._attr_supported_features | SUPPORT_VOLUME_SET
            )
        self._attr_default_tone = default_tone
        self._attr_available_tones = available_tones
        self._attr_volume_level = volume_level

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume_level: float) -> None:
        """Set new volume level."""
        self._attr_volume_level = volume_level
        self.async_write_ha_state()

    async def async_set_default_tone(self, tone: str) -> None:
        """Update default tone."""
        self._attr_default_tone = tone
        self.async_write_ha_state()
