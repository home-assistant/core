"""Demo platform that offers a fake siren device."""
from __future__ import annotations

from typing import Any

from homeassistant.components.siren import SirenEntity
from homeassistant.components.siren.const import (
    SUPPORT_DURATION,
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

SUPPORT_FLAGS = SUPPORT_TURN_OFF | SUPPORT_TURN_ON


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
                available_tones=["fire", "alarm"],
                support_volume_set=True,
                support_duration=True,
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
        available_tones: str | None = None,
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
            self._attr_supported_features |= SUPPORT_TONES
        if support_volume_set:
            self._attr_supported_features |= SUPPORT_VOLUME_SET
        if support_duration:
            self._attr_supported_features |= SUPPORT_DURATION
        self._attr_available_tones = available_tones

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        self._attr_is_on = False
        self.async_write_ha_state()
