"""Demo platform that offers a fake siren device."""

from __future__ import annotations

from typing import Any

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

SUPPORT_FLAGS = SirenEntityFeature.TURN_OFF | SirenEntityFeature.TURN_ON


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo siren devices config entry."""
    async_add_entities(
        [
            DemoSiren(name="Siren"),
            DemoSiren(
                name="Siren with all features",
                available_tones=["fire", "alarm"],
                support_volume_set=True,
                support_duration=True,
            ),
        ]
    )


class DemoSiren(SirenEntity):
    """Representation of a demo siren device."""

    def __init__(
        self,
        name: str,
        available_tones: list[str | int] | None = None,
        support_volume_set: bool = False,
        support_duration: bool = False,
        is_on: bool = True,
    ) -> None:
        """Initialize the siren device."""
        self._attr_name = name
        self._attr_should_poll = False
        self._attr_supported_features = SUPPORT_FLAGS
        self._attr_is_on = is_on
        if available_tones is not None:
            self._attr_supported_features |= SirenEntityFeature.TONES
        if support_volume_set:
            self._attr_supported_features |= SirenEntityFeature.VOLUME_SET
        if support_duration:
            self._attr_supported_features |= SirenEntityFeature.DURATION
        self._attr_available_tones = available_tones

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        self._attr_is_on = False
        self.async_write_ha_state()
