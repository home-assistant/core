"""Preference management for camera component."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Final, cast

from homeassistant.components.stream import Orientation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import (
    DOMAIN,
    PREF_ORIENTATION,
    PREF_PRELOAD_STREAM,
    PREF_USE_STREAM_FOR_STILLS,
)

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1


@dataclass
class DynamicStreamSettings:
    """Stream settings which are managed and updated by the camera entity."""

    preload_stream: bool = False
    orientation: Orientation = Orientation.NO_TRANSFORM


@dataclass
class CameraSettings:
    """All camera settings including stream settings."""

    use_stream_for_stills: bool = False
    stream_settings: DynamicStreamSettings = field(
        default_factory=DynamicStreamSettings
    )

    def flatten(self) -> dict:
        """Flatten the settings and return as a dict."""
        return {
            PREF_USE_STREAM_FOR_STILLS: self.use_stream_for_stills,
            **asdict(self.stream_settings),
        }


class CameraPreferences:
    """Handle camera preferences."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize camera prefs."""
        self._hass = hass
        # The orientation prefs are stored in in the entity registry options
        # The preload_stream prefs are stored in this Store
        self._store = Store[dict[str, dict[str, bool | Orientation]]](
            hass, STORAGE_VERSION, STORAGE_KEY
        )

    async def async_update(
        self,
        entity_id: str,
        *,
        preload_stream: bool | UndefinedType = UNDEFINED,
        orientation: Orientation | UndefinedType = UNDEFINED,
        use_stream_for_stills: bool | UndefinedType = UNDEFINED,
    ) -> CameraSettings:
        """Update camera preferences.

        Also update the DynamicStreamSettings if they exist.
        preload_stream is stored in a Store
        orientation is stored in the Entity Registry

        Returns a dict with the preferences on success.
        Raises HomeAssistantError on failure.
        """
        if preload_stream is not UNDEFINED:
            preload_prefs = await self._store.async_load() or {}
            preload_prefs[entity_id] = {PREF_PRELOAD_STREAM: preload_stream}
            await self._store.async_save(preload_prefs)

        er_settings: dict[str, bool | Orientation] = {}
        if orientation is not UNDEFINED:
            er_settings[PREF_ORIENTATION] = orientation
        if use_stream_for_stills is not UNDEFINED:
            er_settings[PREF_USE_STREAM_FOR_STILLS] = use_stream_for_stills
        if er_settings:
            if (registry := er.async_get(self._hass)).async_get(entity_id):
                registry.async_update_entity_options(entity_id, DOMAIN, er_settings)
            else:
                raise HomeAssistantError(
                    "Orientation and use_stream_for_stills are only supported on entities "
                    "set up through config flows"
                )
        return await self.get_camera_settings(entity_id)

    async def get_camera_settings(self, entity_id: str) -> CameraSettings:
        """Get the CameraSettings for the entity."""
        # Get preload stream setting from prefs
        # Get orientation setting from entity registry
        # Get use_stream_for_stills setting from entity registry
        reg_entry = er.async_get(self._hass).async_get(entity_id)
        er_prefs: Mapping = reg_entry.options.get(DOMAIN, {}) if reg_entry else {}
        preload_prefs = await self._store.async_load() or {}
        preload_stream = cast(
            bool, preload_prefs.get(entity_id, {}).get(PREF_PRELOAD_STREAM, False)
        )
        stream_settings = DynamicStreamSettings(
            preload_stream=preload_stream,
            orientation=er_prefs.get(PREF_ORIENTATION, Orientation.NO_TRANSFORM),
        )
        return CameraSettings(
            er_prefs.get(PREF_USE_STREAM_FOR_STILLS, preload_stream), stream_settings
        )
