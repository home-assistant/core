"""Preference management for camera component."""
from __future__ import annotations

from typing import Final, Union, cast

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
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
        # The orientation prefs are stored in in the entity registry options
        # The preload_stream prefs are stored in this Store
        self._store = Store[dict[str, dict[str, Union[bool, int]]]](
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        # Local copy of the preload_stream prefs
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
    ) -> dict[str, bool | int]:
        """Update camera preferences.

        Returns a dict with the preferences on success.
        Raises HomeAssistantError on failure.
        """
        if preload_stream is not UNDEFINED:
            # Prefs already initialized.
            assert self._prefs is not None
            if not self._prefs.get(entity_id):
                self._prefs[entity_id] = {}
            self._prefs[entity_id][PREF_PRELOAD_STREAM] = preload_stream
            await self._store.async_save(self._prefs)

        if orientation is not UNDEFINED:
            if (registry := er.async_get(self._hass)).async_get(entity_id):
                registry.async_update_entity_options(
                    entity_id, DOMAIN, {PREF_ORIENTATION: orientation}
                )
            else:
                raise HomeAssistantError(
                    "Orientation is only supported on entities set up through config flows"
                )
        return self.get(entity_id).as_dict()

    def get(self, entity_id: str) -> CameraEntityPreferences:
        """Get preferences for an entity."""
        # Prefs are already initialized.
        assert self._prefs is not None
        reg_entry = er.async_get(self._hass).async_get(entity_id)
        er_prefs = reg_entry.options.get(DOMAIN, {}) if reg_entry else {}
        return CameraEntityPreferences(self._prefs.get(entity_id, {}) | er_prefs)
