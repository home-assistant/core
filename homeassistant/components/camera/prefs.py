"""Preference management for camera component."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final, Union, cast

from homeassistant.components.stream import Orientation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import DOMAIN, PREF_ORIENTATION, PREF_PRELOAD_STREAM

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1


@dataclass
class DynamicStreamSettings:
    """Stream settings which are managed and updated by the camera entity."""

    preload_stream: bool = False
    orientation: Orientation = Orientation.NO_TRANSFORM


class CameraPreferences:
    """Handle camera preferences."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize camera prefs."""
        self._hass = hass
        # The orientation prefs are stored in in the entity registry options
        # The preload_stream prefs are stored in this Store
        self._store = Store[dict[str, dict[str, Union[bool, Orientation]]]](
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._dynamic_stream_settings_by_entity_id: dict[
            str, DynamicStreamSettings
        ] = {}

    async def async_update(
        self,
        entity_id: str,
        *,
        preload_stream: bool | UndefinedType = UNDEFINED,
        orientation: Orientation | UndefinedType = UNDEFINED,
    ) -> dict[str, bool | Orientation]:
        """Update camera preferences.

        Also update the DynamicStreamSettings if they exist.
        preload_stream is stored in a Store
        orientation is stored in the Entity Registry

        Returns a dict with the preferences on success.
        Raises HomeAssistantError on failure.
        """
        dynamic_stream_settings = self._dynamic_stream_settings_by_entity_id.get(
            entity_id
        )
        if preload_stream is not UNDEFINED:
            if dynamic_stream_settings:
                dynamic_stream_settings.preload_stream = preload_stream
            preload_prefs = await self._store.async_load() or {}
            preload_prefs[entity_id] = {PREF_PRELOAD_STREAM: preload_stream}
            await self._store.async_save(preload_prefs)

        if orientation is not UNDEFINED:
            if (registry := er.async_get(self._hass)).async_get(entity_id):
                registry.async_update_entity_options(
                    entity_id, DOMAIN, {PREF_ORIENTATION: orientation}
                )
            else:
                raise HomeAssistantError(
                    "Orientation is only supported on entities set up through config flows"
                )
            if dynamic_stream_settings:
                dynamic_stream_settings.orientation = orientation
        return asdict(await self.get_dynamic_stream_settings(entity_id))

    async def get_dynamic_stream_settings(
        self, entity_id: str
    ) -> DynamicStreamSettings:
        """Get the DynamicStreamSettings for the entity."""
        if settings := self._dynamic_stream_settings_by_entity_id.get(entity_id):
            return settings
        # Get preload stream setting from prefs
        # Get orientation setting from entity registry
        reg_entry = er.async_get(self._hass).async_get(entity_id)
        er_prefs = reg_entry.options.get(DOMAIN, {}) if reg_entry else {}
        preload_prefs = await self._store.async_load() or {}
        settings = DynamicStreamSettings(
            preload_stream=cast(
                bool, preload_prefs.get(entity_id, {}).get(PREF_PRELOAD_STREAM, False)
            ),
            orientation=er_prefs.get(PREF_ORIENTATION, Orientation.NO_TRANSFORM),
        )
        self._dynamic_stream_settings_by_entity_id[entity_id] = settings
        return settings
