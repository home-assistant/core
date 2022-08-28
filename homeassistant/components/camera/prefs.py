"""Preference management for camera component."""
from __future__ import annotations

from typing import Final, Union, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import DOMAIN, PREF_ORIENTATION, PREF_PRELOAD_STREAM

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1


class CameraEntityPreferences:
    """Handle preferences for camera entity."""

    def __init__(self, prefs: dict[str, bool | int]) -> None:
        """Initialize prefs."""
        self._prefs = prefs

    def as_dict(self) -> dict[str, bool | int]:
        """Return dictionary version."""
        return self._prefs

    @property
    def preload_stream(self) -> bool:
        """Return if stream is loaded on hass start."""
        return cast(bool, self._prefs.get(PREF_PRELOAD_STREAM, False))

    @property
    def orientation(self) -> int:
        """Return the current stream orientation settings."""
        return self._prefs.get(PREF_ORIENTATION, 1)


class CameraPreferences:
    """Handle camera preferences."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize camera prefs."""
        self._hass = hass
        self._store = Store[dict[str, dict[str, Union[bool, int]]]](
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._prefs: dict[str, dict[str, bool | int]] | None = None

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
        orientation: int | UndefinedType = UNDEFINED,
        stream_options: dict[str, str] | UndefinedType = UNDEFINED,
    ) -> None:
        """Update camera preferences."""
        # Prefs already initialized.
        assert self._prefs is not None
        if not self._prefs.get(entity_id):
            self._prefs[entity_id] = {}

        for key, value in (
            (PREF_PRELOAD_STREAM, preload_stream),
            (PREF_ORIENTATION, orientation),
        ):
            if value is not UNDEFINED:
                self._prefs[entity_id][key] = value

        await self._store.async_save(self._prefs)

    def get(self, entity_id: str) -> CameraEntityPreferences:
        """Get preferences for an entity."""
        # Prefs are already initialized.
        assert self._prefs is not None
        return CameraEntityPreferences(self._prefs.get(entity_id, {}))
