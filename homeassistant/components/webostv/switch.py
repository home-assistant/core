"""Support for LG webOS TV switch."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WebOsTvConfigEntry
from .entity import WebOsTvEntity, cmd

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG webOS TV switch platform."""
    async_add_entities([LgWebOSScreenSwitchEntity(entry)])


class LgWebOSScreenSwitchEntity(WebOsTvEntity, SwitchEntity):
    """Representation of a LG webOS TV Screen Switch."""

    _attr_translation_key = "screen"

    def __init__(self, entry: WebOsTvConfigEntry) -> None:
        """Initialize the screen switch entity."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.unique_id}_screen"

    @property
    @override
    def available(self) -> bool:
        """Return true if the entity is available."""
        return super().available and self._client.tv_state.is_on

    @property
    @override
    def is_on(self) -> bool:
        """Return true if screen is on."""
        return self._client.tv_state.is_screen_on

    @cmd
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the screen on."""
        await self._client.set_screen_state(True)

    @cmd
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen off."""
        await self._client.set_screen_state(False)
