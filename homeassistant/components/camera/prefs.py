"""Preference management for camera component."""
from .const import DOMAIN, PREF_PRELOAD_STREAM

# mypy: allow-untyped-defs, no-check-untyped-defs

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
_UNDEF = object()


class CameraEntityPreferences:
    """Handle preferences for camera entity."""

    def __init__(self, prefs):
        """Initialize prefs."""
        self._prefs = prefs

    def as_dict(self):
        """Return dictionary version."""
        return self._prefs

    @property
    def preload_stream(self):
        """Return if stream is loaded on hass start."""
        return self._prefs.get(PREF_PRELOAD_STREAM, False)


class CameraPreferences:
    """Handle camera preferences."""

    def __init__(self, hass):
        """Initialize camera prefs."""
        self._hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._prefs = None

    async def async_initialize(self):
        """Finish initializing the preferences."""
        prefs = await self._store.async_load()

        if prefs is None:
            prefs = {}

        self._prefs = prefs

    async def async_update(
        self, entity_id, *, preload_stream=_UNDEF, stream_options=_UNDEF
    ):
        """Update camera preferences."""
        if not self._prefs.get(entity_id):
            self._prefs[entity_id] = {}

        for key, value in ((PREF_PRELOAD_STREAM, preload_stream),):
            if value is not _UNDEF:
                self._prefs[entity_id][key] = value

        await self._store.async_save(self._prefs)

    def get(self, entity_id):
        """Get preferences for an entity."""
        return CameraEntityPreferences(self._prefs.get(entity_id, {}))
