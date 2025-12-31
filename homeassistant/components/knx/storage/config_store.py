"""KNX entity configuration store."""

from abc import ABC, abstractmethod
from copy import deepcopy
import logging
from typing import Any, Final, TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.util.ulid import ulid_now

from .. import create_and_register_knx_exposure
from ..const import DOMAIN, KNX_ADDRESS
from ..expose import create_knx_exposure
from ..services import get_knx_module
from .const import CONF_DATA, CONF_GA_WRITE
from .migration import migrate_1_to_2, migrate_2_1_to_2_2

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION: Final = 2
STORAGE_VERSION_MINOR: Final = 2
STORAGE_KEY: Final = f"{DOMAIN}/config_store.json"

type KNXPlatformStoreModel = dict[str, dict[str, Any]]  # unique_id: configuration
type KNXEntityStoreModel = dict[
    str, KNXPlatformStoreModel
]  # platform: KNXPlatformStoreModel
type KNXExposeStoreModel = KNXPlatformStoreModel


class KNXConfigStoreModel(TypedDict):
    """Represent KNX configuration store data."""

    entities: KNXEntityStoreModel
    expose: KNXExposeStoreModel


class PlatformControllerBase(ABC):
    """Entity platform controller base class."""

    @abstractmethod
    async def create_entity(self, unique_id: str, config: dict[str, Any]) -> None:
        """Create a new entity."""

    @abstractmethod
    async def update_entity(
        self, entity_entry: er.RegistryEntry, config: dict[str, Any]
    ) -> None:
        """Update an existing entities configuration."""


class _KNXConfigStoreStorage(Store[KNXConfigStoreModel]):
    """Storage handler for KNXConfigStore."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_major_version == 1:
            # version 2.1 introduced in 2025.8
            migrate_1_to_2(old_data)

        if old_major_version <= 2 and old_minor_version < 2:
            # version 2.2 introduced in 2025.9.2
            migrate_2_1_to_2_2(old_data)

        return old_data


class KNXConfigStore:
    """Manage KNX config store data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize config store."""
        self.hass = hass
        self.config_entry = config_entry
        self._store = _KNXConfigStoreStorage(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        )
        self.data = KNXConfigStoreModel(entities={}, expose={})
        self._platform_controllers: dict[Platform, PlatformControllerBase] = {}

    async def load_data(self) -> None:
        """Load config store data from storage."""
        if data := await self._store.async_load():
            data.setdefault("expose", {})
            self.data = KNXConfigStoreModel(**data)
            _LOGGER.debug(
                "Loaded KNX config data from storage. %s entity platforms",
                len(self.data["entities"]),
            )

    def add_platform(
        self, platform: Platform, controller: PlatformControllerBase
    ) -> None:
        """Add platform controller."""
        self._platform_controllers[platform] = controller

    async def create_entity(
        self, platform: Platform, data: dict[str, Any]
    ) -> str | None:
        """Create a new entity."""
        platform_controller = self._platform_controllers[platform]
        unique_id = f"knx_es_{ulid_now()}"
        await platform_controller.create_entity(unique_id, data)
        # store data after entity was added to be sure config didn't raise exceptions
        self.data["entities"].setdefault(platform, {})[unique_id] = data
        await self._store.async_save(self.data)

        entity_registry = er.async_get(self.hass)
        return entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)

    @callback
    def get_entity_config(self, entity_id: str) -> dict[str, Any]:
        """Return KNX entity configuration."""
        entity_registry = er.async_get(self.hass)
        if (entry := entity_registry.async_get(entity_id)) is None:
            raise ConfigStoreException(f"Entity not found: {entity_id}")
        try:
            return {
                CONF_PLATFORM: entry.domain,
                CONF_DATA: self.data["entities"][entry.domain][entry.unique_id],
            }
        except KeyError as err:
            raise ConfigStoreException(f"Entity data not found: {entity_id}") from err

    async def update_entity(
        self, platform: Platform, entity_id: str, data: dict[str, Any]
    ) -> None:
        """Update an existing entity."""
        platform_controller = self._platform_controllers[platform]
        entity_registry = er.async_get(self.hass)
        if (entry := entity_registry.async_get(entity_id)) is None:
            raise ConfigStoreException(f"Entity not found: {entity_id}")
        unique_id = entry.unique_id
        if (
            platform not in self.data["entities"]
            or unique_id not in self.data["entities"][platform]
        ):
            raise ConfigStoreException(
                f"Entity not found in storage: {entity_id} - {unique_id}"
            )
        await platform_controller.update_entity(entry, data)
        # store data after entity is added to make sure config doesn't raise exceptions
        self.data["entities"][platform][unique_id] = data
        await self._store.async_save(self.data)

    async def delete_entity(self, entity_id: str) -> None:
        """Delete an existing entity."""
        entity_registry = er.async_get(self.hass)
        if (entry := entity_registry.async_get(entity_id)) is None:
            raise ConfigStoreException(f"Entity not found: {entity_id}")
        try:
            del self.data["entities"][entry.domain][entry.unique_id]
        except KeyError as err:
            raise ConfigStoreException(
                f"Entity not found in {entry.domain}: {entry.unique_id}"
            ) from err
        entity_registry.async_remove(entity_id)
        await self._store.async_save(self.data)

    def get_entity_entries(self) -> list[er.RegistryEntry]:
        """Get entity_ids of all UI configured entities."""
        entity_registry = er.async_get(self.hass)
        unique_ids = {
            uid for platform in self.data["entities"].values() for uid in platform
        }
        return [
            registry_entry
            for registry_entry in er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )
            if registry_entry.unique_id in unique_ids
        ]

    async def create_expose(self, data: dict[str, Any]) -> str:
        """Create a new expose and return its address."""
        address = str(data[KNX_ADDRESS][CONF_GA_WRITE])
        if address in self.data["expose"]:
            raise ValueError(f'There is already an exposure registered at address {address}')
        knx_module = get_knx_module(self.hass)
        exposure = create_and_register_knx_exposure(self.hass, knx_module.xknx, data)
        knx_module.ui_exposures[address] = exposure
        # store data after the expose was added to be sure config didn't raise exceptions
        self.data["expose"][address] = data
        await self._store.async_save(self.data)
        return address

    @callback
    def get_expose_config(self, address: str) -> dict[str, Any]:
        """Return KNX expose configuration."""
        knx_module = get_knx_module(self.hass)
        if knx_module.ui_exposures.get(address) is None:
            raise ConfigStoreException(f"Expose not found: {address}")
        try:
            return deepcopy(self.data["expose"][address])
        except KeyError as err:
            raise ConfigStoreException(f"Expose data not found: {address}") from err

    async def update_expose(self, data: dict[str, Any]) -> str:
        """Update an existing expose and return its address."""
        address = str(data[KNX_ADDRESS][CONF_GA_WRITE])
        knx_module = get_knx_module(self.hass)
        if (existing_expose := knx_module.ui_exposures.get(address)) is None:
            raise ConfigStoreException(f"Expose not found: {address}")
        if address not in self.data["expose"]:
            raise ConfigStoreException(
                f"Expose not found in storage: {address}"
            )
        updated_expose = create_knx_exposure(self.hass, knx_module.xknx, data)
        # remove previous expose only after ensuring the config doesn't raise exceptions
        del knx_module.ui_exposures[address]
        existing_expose.async_remove()
        updated_expose.async_register()
        knx_module.ui_exposures[address] = updated_expose
        # store data after the expose is added to make sure config doesn't raise exceptions
        self.data["expose"][address] = data
        await self._store.async_save(self.data)
        return address

    async def delete_expose(self, address: str) -> None:
        """Delete an existing expose."""
        knx_module = get_knx_module(self.hass)
        if (expose := knx_module.ui_exposures.pop(address)) is None:
            raise ConfigStoreException(f"Expose not found: {address}")
        try:
            del self.data["expose"][address]
        except KeyError as err:
            raise ConfigStoreException(
                f"Expose not found: {address}"
            ) from err
        expose.async_remove()
        await self._store.async_save(self.data)

    def get_expose_entries(self) -> dict[str, dict[str, Any]]:
        """Get the data of all UI configured expose entries."""
        return deepcopy(self.data["expose"])


class ConfigStoreException(Exception):
    """KNX config store exception."""
