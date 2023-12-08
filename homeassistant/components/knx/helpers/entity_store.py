"""KNX entity configuration store."""
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.util.uuid import random_uuid_hex

from ..const import DOMAIN

if TYPE_CHECKING:
    from ..knx_entity import KnxEntity

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}/entity_store.json"

KNXPlatformStoreModel = dict[str, dict[str, Any]]  # unique_id: configuration
KNXEntityStoreModel = dict[
    str, KNXPlatformStoreModel
]  # platform: KNXPlatformStoreModel


class KNXEntityStore:
    """Manage KNX entity store data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize project data."""
        self.hass = hass
        self._store = Store[KNXEntityStoreModel](hass, STORAGE_VERSION, STORAGE_KEY)

        self.data: KNXEntityStoreModel = {}
        # entities and async_add_entity are filled by platform setups
        self.entities: dict[str, KnxEntity] = {}  # unique_id as key
        self.async_add_entity: dict[
            Platform, Callable[[str, dict[str, Any]], None]
        ] = {}

    async def load_data(self) -> None:
        """Load project data from storage."""
        self.data = await self._store.async_load() or {}
        _LOGGER.debug(
            "Loaded KNX entity data for %s entity platforms from storage",
            len(self.data),
        )

    async def create_entitiy(self, platform: Platform, data: dict[str, Any]) -> None:
        """Create a new entity."""
        if platform not in self.async_add_entity:
            raise EntityStoreException(f"Entity platform not ready: {platform}")
        unique_id = f"knx_es_{random_uuid_hex()}"
        if unique_id in self.data.setdefault(platform, {}):
            raise EntityStoreException("Unique id already used.")
        self.async_add_entity[platform](unique_id, data)
        # store data after entity was added to be sure config didn't raise exceptions
        self.data[platform][unique_id] = data
        await self._store.async_save(self.data)

    @callback
    def get_entity_config(self, entity_id: str) -> dict[str, Any]:
        """Return KNX entity configuration."""
        entity_registry = er.async_get(self.hass)
        if (entry := entity_registry.async_get(entity_id)) is None:
            raise EntityStoreException(f"Entity not found: {entity_id}")
        try:
            return {
                "platform": entry.domain,
                "unique_id": entry.unique_id,
                "data": self.data[entry.domain][entry.unique_id],
            }
        except KeyError as err:
            raise EntityStoreException(f"Entity data not found: {entity_id}") from err

    async def update_entity(
        self, platform: Platform, unique_id: str, data: dict[str, Any]
    ) -> None:
        """Update an existing entity."""
        if platform not in self.async_add_entity:
            raise EntityStoreException(f"Entity platform not ready: {platform}")
        if platform not in self.data or unique_id not in self.data[platform]:
            raise EntityStoreException(f"Entity not found in {platform}: {unique_id}")
        await self.entities.pop(unique_id).async_remove()
        self.async_add_entity[platform](unique_id, data)
        # store data after entity is added to make sure config doesn't raise exceptions
        self.data[platform][unique_id] = data
        await self._store.async_save(self.data)

    async def delete_entity(self, entity_id: str) -> None:
        """Delete an existing entity."""
        entity_registry = er.async_get(self.hass)
        if (entry := entity_registry.async_get(entity_id)) is None:
            raise EntityStoreException(f"Entity not found: {entity_id}")
        try:
            del self.data[entry.domain][entry.unique_id]
        except KeyError as err:
            raise EntityStoreException(
                f"Entity not found in {entry.domain}: {entry.unique_id}"
            ) from err
        try:
            del self.entities[entry.unique_id]
        except KeyError:
            _LOGGER.warning("Entity not initialized when deleted: %s", entity_id)
        entity_registry.async_remove(entity_id)
        await self._store.async_save(self.data)

    def get_entity_entries(self) -> list[er.RegistryEntry]:
        """Get entity_ids of all configured entities by platform."""
        return [
            entity.registry_entry
            for entity in self.entities.values()
            if entity.registry_entry is not None
        ]


class EntityStoreException(Exception):
    """KNX entity store exception."""
