"""Nanoleaf hub."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aionanoleaf import EffectsEvent, Nanoleaf, StateEvent

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .light import NanoleafLight


class NanoleafHub:
    """Nanoleaf hub."""

    def __init__(self, hass: HomeAssistant, nanoleaf: Nanoleaf) -> None:
        """Initialize the hub."""
        self._hass = hass
        self._nanoleaf = nanoleaf
        self._event_listener = asyncio.create_task(
            self._nanoleaf.listen_events(
                state_callback=self._callback_update_light_state,
                effects_callback=self._callback_update_light_state,
            )
        )
        self._light_entity: NanoleafLight | None = None

    @property
    def nanoleaf(self) -> Nanoleaf:
        """Return the nanoleaf."""
        return self._nanoleaf

    async def _callback_update_light_state(
        self, event: StateEvent | EffectsEvent
    ) -> None:
        """Receive state and effect event."""
        if self._light_entity is not None:
            self._light_entity.async_write_ha_state()

    async def set_light_entity(self, light_entity: NanoleafLight) -> None:
        """Set light entity."""
        self._light_entity = light_entity

    async def unload(self) -> None:
        """Unload the hub."""
        self._event_listener.cancel()
