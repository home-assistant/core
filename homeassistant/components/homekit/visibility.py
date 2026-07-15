"""Manage storage of HomeKit input visibility state.

Persists which input sources the user has hidden ("Show in Home" off in the
Apple Home app) per entity. This lives in a per-entry HomeKit storage file
rather than the config entry so a toggle does not rewrite the whole config
entries store, mirroring how aid and iid allocations are stored.
"""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .util import get_visibility_storage_filename_for_entry_id

VISIBILITY_STORAGE_VERSION = 1
VISIBILITY_SAVE_DELAY = 2

HIDDEN_SOURCES_KEY = "hidden_sources"


class AccessoryVisibilityStorage:
    """Hold the set of hidden input sources per entity for a HomeKit bridge."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Create a new visibility store."""
        self.hass = hass
        self._entry_id = entry_id
        self.store: Store | None = None
        self._hidden_sources: dict[str, list[str]] = {}

    async def async_initialize(self) -> None:
        """Load the latest visibility data."""
        filename = get_visibility_storage_filename_for_entry_id(self._entry_id)
        self.store = Store(self.hass, VISIBILITY_STORAGE_VERSION, filename)
        if not (raw_storage := await self.store.async_load()):
            return
        assert isinstance(raw_storage, dict)
        self._hidden_sources = raw_storage.get(HIDDEN_SOURCES_KEY, {})

    def get_hidden_sources(self, entity_id: str) -> list[str]:
        """Return the persisted hidden sources for an entity."""
        return list(self._hidden_sources.get(entity_id, []))

    @callback
    def async_set_hidden_sources(self, entity_id: str, sources: set[str]) -> None:
        """Update the hidden sources for an entity and schedule a save."""
        if sources:
            self._hidden_sources[entity_id] = sorted(sources)
        else:
            self._hidden_sources.pop(entity_id, None)
        self.async_schedule_save()

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the visibility store."""
        assert self.store is not None
        self.store.async_delay_save(self._data_to_save, VISIBILITY_SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, dict[str, list[str]]]:
        """Return data of the visibility map to store in a file."""
        return {HIDDEN_SOURCES_KEY: self._hidden_sources}
