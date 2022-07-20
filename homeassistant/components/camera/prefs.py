"""Preference management for camera component."""
from __future__ import annotations

from typing import Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import DOMAIN, PREF_PRELOAD_STREAM

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1


class CameraEntityPreferences:
    """Handle preferences for camera entity."""

    def __init__(self, prefs: dict[str, bool]) -> None:
        """Initialize prefs."""
        self._prefs = prefs

    def as_dict(self) -> dict[str, bool]:
        """Return dictionary version."""
        return self._prefs

    @property
    def preload_stream(self) -> bool:
        """Return if stream is loaded on hass start."""
        return self._prefs.get(PREF_PRELOAD_STREAM, False)


class CameraPreferences:
    """Handle camera preferences."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize camera prefs."""
        self._hass = hass
        self._store = Store[dict[str, dict[str, bool]]](
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._prefs: dict[str, dict[str, bool]] | None = None

    async def async_initialize(self) -> None:
        """Finish initializing the preferences."""
        if (prefs := await self._store.async_load()) is None:
            prefs = {}

        self._prefs = prefs

    async def async_update(
        self,
        entity_id: str,
        *,
        preload_stream: bool | UndefinedType = UNDEFINED,
        stream_options: dict[str, str] | UndefinedType = UNDEFINED,
    ) -> None:
        """Update camera preferences."""
        # Prefs already initialized.
        assert self._prefs is not None
        if not self._prefs.get(entity_id):
            self._prefs[entity_id] = {}

        for key, value in ((PREF_PRELOAD_STREAM, preload_stream),):
            if value is not UNDEFINED:
                self._prefs[entity_id][key] = value

        await self._store.async_save(self._prefs)

    def get(self, entity_id: str) -> CameraEntityPreferences:
        """Get preferences for an entity."""
        # Prefs are already initialized.
        assert self._prefs is not None
        return CameraEntityPreferences(self._prefs.get(entity_id, {}))
