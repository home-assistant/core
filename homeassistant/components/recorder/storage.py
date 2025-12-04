"""Storage management for recorder exclusions."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY_EXCLUSIONS, STORAGE_VERSION_EXCLUSIONS

_LOGGER = logging.getLogger(__name__)


class RecorderExclusionsStore:
    """Manage storage for entity exclusions configured via UI.

    This store manages entity exclusions that are set via the UI/WebSocket API.
    These exclusions are merged with YAML-configured exclusions at runtime.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the exclusions store."""
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION_EXCLUSIONS,
            STORAGE_KEY_EXCLUSIONS,
        )
        self._excluded_entities: set[str] = set()
        self._loaded = False

    @property
    def excluded_entities(self) -> set[str]:
        """Return the set of excluded entity IDs."""
        return self._excluded_entities

    async def async_load(self) -> None:
        """Load exclusions from storage."""
        if self._loaded:
            return

        data = await self._store.async_load()
        if data is not None:
            self._excluded_entities = set(data.get("excluded_entities", []))
        self._loaded = True
        _LOGGER.debug("Loaded %d entity exclusions from storage", len(self._excluded_entities))

    async def async_save(self) -> None:
        """Save exclusions to storage."""
        await self._store.async_save(
            {"excluded_entities": sorted(self._excluded_entities)}
        )
        _LOGGER.debug("Saved %d entity exclusions to storage", len(self._excluded_entities))

    @callback
    def add_exclusion(self, entity_id: str) -> bool:
        """Add an entity to the exclusion list.

        Returns True if the entity was added, False if already excluded.
        """
        if entity_id in self._excluded_entities:
            return False
        self._excluded_entities.add(entity_id)
        return True

    @callback
    def remove_exclusion(self, entity_id: str) -> bool:
        """Remove an entity from the exclusion list.

        Returns True if the entity was removed, False if not in list.
        """
        if entity_id not in self._excluded_entities:
            return False
        self._excluded_entities.discard(entity_id)
        return True

    @callback
    def is_excluded(self, entity_id: str) -> bool:
        """Check if an entity is excluded via storage."""
        return entity_id in self._excluded_entities

    def get_exclusions_data(self) -> dict[str, str]:
        """Get exclusions with their source for API response.

        Returns a dict mapping entity_id to source ("storage").
        """
        return dict.fromkeys(self._excluded_entities, "storage")
