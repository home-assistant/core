"""KNX entity configuration store."""

from abc import ABC, abstractmethod
from collections.abc import Callable
import dataclasses
from functools import partial
import logging
from typing import (
    Annotated,
    Any,
    Final,
    TypedDict,
    get_args,
    get_origin,
    get_type_hints,
    override,
)

from probatio import Key

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.util.ulid import ulid_now

from ..const import DOMAIN, KNX_MODULE_KEY
from ..repairs import (
    async_create_entity_validation_issue,
    async_create_expose_validation_issue,
    async_create_time_server_validation_issue,
)
from . import migration
from .const import CONF_DATA, CONF_ENTITY
from .entity_store_schema import KnxEntityData
from .entity_store_validation import (
    EntityStoreValidationException,
    validate_entity_data,
)
from .expose_controller import (
    ExposeConfig,
    KNXExposeStoreConfigModel,
    KNXExposeStoreModel,
    validate_stored_expose_config,
)
from .knx_selector import (
    GroupAddressSelector,
    GroupSelect,
    KnxPayloadSelector,
    KnxSelectOptionsSelector,
    knx_selector_in,
)
from .time_server import (
    KNXTimeServerStoreModel,
    TimeServerConfig,
    validate_time_server_data,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION: Final = 2
STORAGE_VERSION_MINOR: Final = 5
STORAGE_KEY: Final = f"{DOMAIN}/config_store.json"

type KNXPlatformStoreModel = dict[str, dict[str, Any]]  # unique_id: configuration
type KNXEntityStoreModel = dict[
    str, KNXPlatformStoreModel
]  # platform: KNXPlatformStoreModel


class KNXConfigStoreModel(TypedDict):
    """Represent KNX configuration store data."""

    entities: KNXEntityStoreModel
    expose: KNXExposeStoreModel
    time_server: KNXTimeServerStoreModel


def to_storage_dict(data: KnxEntityData[Any]) -> dict[str, Any]:
    """Render validated entity data to its JSON serializable storage form."""
    return {
        CONF_ENTITY: dataclasses.asdict(data.entity),
        DOMAIN: _knx_to_storage(data.knx),
    }


def expose_to_storage(config: ExposeConfig) -> KNXExposeStoreConfigModel:
    """Render a validated expose configuration to its storage form.

    Options left at their default are omitted - the frontend treats a present
    key as set.
    """
    return _knx_to_storage(config, sparse=True)  # type: ignore[return-value]


def time_server_to_storage(config: TimeServerConfig) -> KNXTimeServerStoreModel:
    """Render a validated time server configuration to its storage form.

    Unset group addresses are omitted, like the frontend sends them.
    """
    return _knx_to_storage(config, sparse=True)  # type: ignore[return-value]


def _knx_to_storage(config: Any, *, sparse: bool = False) -> dict[str, Any]:
    """Render a typed config to its storage form.

    `sparse` omits fields left at their default.
    """
    data: dict[str, Any] = {}
    for name, default, encode in _storage_encoders(type(config), sparse):
        value = getattr(config, name)
        if sparse and value == default:
            continue
        data[name] = encode(value)
    return data


def _unchanged(value: Any) -> Any:
    return value


def _group_select_to_storage(value: Any, *, sparse: bool) -> dict[str, Any] | None:
    return None if value is None else _knx_to_storage(value, sparse=sparse)


def _list_to_storage(value: list[Any], *, sparse: bool) -> list[dict[str, Any]]:
    return [_knx_to_storage(item, sparse=sparse) for item in value]


type _StorageEncoders = tuple[tuple[str, Any, Callable[[Any], Any]], ...]
_STORAGE_ENCODERS: dict[tuple[type, bool], _StorageEncoders] = {}


def _storage_encoders(config_type: type, sparse: bool) -> _StorageEncoders:
    """Return name, default and a storage encoder per field of a typed config.

    Section fields are dropped, group addresses and payloads are rendered by
    their selector, group select options and lists of typed configs by their
    own encoders.
    """
    if (cached := _STORAGE_ENCODERS.get((config_type, sparse))) is not None:
        return cached
    hints = get_type_hints(config_type, include_extras=True)
    encoders: list[tuple[str, Any, Callable[[Any], Any]]] = []
    for dc_field in dataclasses.fields(config_type):
        hint = hints[dc_field.name]
        if get_origin(hint) is Annotated:
            field_type, *metadata = get_args(hint)
        else:
            field_type, metadata = hint, []
        if any(isinstance(item, Key) and item.remove for item in metadata):
            continue
        field_selector = knx_selector_in(metadata)
        encode: Callable[[Any], Any]
        if isinstance(
            field_selector,
            (GroupAddressSelector, KnxPayloadSelector, KnxSelectOptionsSelector),
        ):
            encode = field_selector.to_storage
        elif isinstance(field_selector, GroupSelect):
            encode = partial(_group_select_to_storage, sparse=sparse)
        elif get_origin(field_type) is list and dataclasses.is_dataclass(
            get_args(field_type)[0]
        ):
            encode = partial(_list_to_storage, sparse=sparse)
        else:
            encode = _unchanged
        encoders.append((dc_field.name, dc_field.default, encode))
    _STORAGE_ENCODERS[config_type, sparse] = tuple(encoders)
    return _STORAGE_ENCODERS[config_type, sparse]


class PlatformControllerBase(ABC):
    """Entity platform controller base class."""

    @abstractmethod
    async def create_entity(self, unique_id: str, config: KnxEntityData[Any]) -> None:
        """Create a new entity."""

    @abstractmethod
    async def update_entity(
        self, entity_entry: er.RegistryEntry, config: KnxEntityData[Any]
    ) -> None:
        """Update an existing entities configuration."""


class _KNXConfigStoreStorage(Store[KNXConfigStoreModel]):
    """Storage handler for KNXConfigStore."""

    @override
    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_major_version == 1:
            # version 2.1 introduced in 2025.8
            migration.migrate_1_to_2(old_data)

        if old_major_version <= 2 and old_minor_version < 2:
            # version 2.2 introduced in 2025.9.2
            migration.migrate_2_1_to_2_2(old_data)

        if old_major_version <= 2 and old_minor_version < 3:
            # version 2.3 introduced in 2026.3
            migration.migrate_2_2_to_2_3(old_data)

        if old_major_version <= 2 and old_minor_version < 4:
            # version 2.4 introduced in 2026.5
            migration.migrate_2_3_to_2_4(old_data)

        if old_major_version <= 2 and old_minor_version < 5:
            # version 2.5 introduced in 2026.10
            migration.migrate_2_4_to_2_5(old_data)

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
        self.data = KNXConfigStoreModel(  # initialize with default structure
            entities={},
            expose={},
            time_server={},
        )
        self._platform_controllers: dict[Platform, PlatformControllerBase] = {}

    async def load_data(self) -> None:
        """Load config store data from storage."""
        if data := await self._store.async_load():
            self.data = KNXConfigStoreModel(**data)
            _LOGGER.debug(
                "Loaded KNX config data from storage. %s entity platforms",
                len(self.data["entities"]),
            )
            _LOGGER.debug(
                "Loaded KNX config data from storage. %s exposes",
                len(self.data["expose"]),
            )

    def add_platform(
        self, platform: Platform, controller: PlatformControllerBase
    ) -> None:
        """Add platform controller."""
        self._platform_controllers[platform] = controller

    @callback
    def get_entity_configs[KnxT](
        self, platform: Platform, config_type: type[KnxT]
    ) -> dict[str, KnxEntityData[KnxT]]:
        """Return validated entity configurations for a platform.

        Invalid configurations are reported as a repair issue and stay in
        `self.data` so they aren't dropped from storage.
        """
        validated: dict[str, KnxEntityData[KnxT]] = {}
        invalid: list[str] = []
        for unique_id, config in self.data["entities"].get(platform, {}).items():
            try:
                result = validate_entity_data(
                    {CONF_PLATFORM: platform, CONF_DATA: config}
                )
            except EntityStoreValidationException:
                invalid.append(unique_id)
                continue
            data: KnxEntityData[KnxT] = result[CONF_DATA]
            if not isinstance(data.knx, config_type):
                raise TypeError(
                    f"{platform} schema yields {type(data.knx).__name__},"
                    f" not {config_type.__name__}"
                )
            validated[unique_id] = data
        if invalid:
            async_create_entity_validation_issue(self.hass, platform, invalid)
        return validated

    async def create_entity(
        self, platform: Platform, data: KnxEntityData[Any]
    ) -> str | None:
        """Create a new entity."""
        platform_controller = self._platform_controllers[platform]
        unique_id = f"knx_es_{ulid_now()}"
        await platform_controller.create_entity(unique_id, data)
        # store data after entity was added to be sure config didn't raise exceptions
        self.data["entities"].setdefault(platform, {})[unique_id] = to_storage_dict(
            data
        )
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
        self, platform: Platform, entity_id: str, data: KnxEntityData[Any]
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
        self.data["entities"][platform][unique_id] = to_storage_dict(data)
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

    def get_entity_uids(self) -> set[str]:
        """Return unique_ids of all UI configured entities."""
        return {uid for platform in self.data["entities"].values() for uid in platform}

    def get_entity_entries(self) -> list[er.RegistryEntry]:
        """Get entity_ids of all UI configured entities."""
        entity_registry = er.async_get(self.hass)
        unique_ids = self.get_entity_uids()
        return [
            registry_entry
            for registry_entry in er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )
            if registry_entry.unique_id in unique_ids
        ]

    @callback
    def get_exposes(self) -> dict[str, ExposeConfig]:
        """Return validated entity state expose configurations.

        Invalid configurations are reported as a repair issue and stay in
        `self.data` so they aren't dropped from storage.
        """
        validated: dict[str, ExposeConfig] = {}
        invalid: list[str] = []
        for entity_id, config in self.data["expose"].items():
            try:
                validated[entity_id] = validate_stored_expose_config(dict(config))
            except EntityStoreValidationException:
                invalid.append(entity_id)
        if invalid:
            async_create_expose_validation_issue(self.hass, invalid)
        return validated

    def get_expose_groups(self) -> dict[str, list[str]]:
        """Return KNX entity state exposes and their group addresses."""
        return {
            entity_id: [option["ga"]["write"] for option in config["options"]]
            for entity_id, config in self.data["expose"].items()
        }

    def get_expose_config(self, entity_id: str) -> KNXExposeStoreConfigModel:
        """Return KNX entity state expose configuration and notes for an entity."""
        return self.data["expose"].get(entity_id, KNXExposeStoreConfigModel(options=[]))

    async def update_expose(self, entity_id: str, expose_config: ExposeConfig) -> None:
        """Update KNX expose configuration for an entity.

        Args:
            entity_id: The entity ID to configure.
            expose_config: Expose configuration with options and optional notes.
        """
        knx_module = self.hass.data[KNX_MODULE_KEY]
        expose_controller = knx_module.ui_expose_controller

        expose_controller.update_entity_expose(
            self.hass, knx_module.xknx, entity_id, expose_config
        )

        self.data["expose"][entity_id] = expose_to_storage(expose_config)
        await self._store.async_save(self.data)

    async def delete_expose(self, entity_id: str) -> None:
        """Delete KNX expose configuration for an entity."""
        knx_module = self.hass.data[KNX_MODULE_KEY]
        expose_controller = knx_module.ui_expose_controller
        expose_controller.remove_entity_expose(entity_id)

        try:
            del self.data["expose"][entity_id]
        except KeyError as err:
            raise ConfigStoreException(
                f"Entity not found in expose configuration: {entity_id}"
            ) from err
        await self._store.async_save(self.data)

    @callback
    def get_time_server_config(self) -> KNXTimeServerStoreModel:
        """Return the stored KNX time server configuration."""
        return self.data["time_server"]

    @callback
    def get_time_server(self) -> TimeServerConfig | None:
        """Return the validated time server configuration.

        An invalid configuration is reported as a repair issue and stays in
        `self.data` so it isn't dropped from storage.
        """
        try:
            return validate_time_server_data(dict(self.data["time_server"]))
        except EntityStoreValidationException:
            async_create_time_server_validation_issue(self.hass)
            return None

    async def update_time_server_config(self, config: TimeServerConfig) -> None:
        """Update time server configuration."""
        self.data["time_server"] = time_server_to_storage(config)
        knx_module = self.hass.data[KNX_MODULE_KEY]
        if knx_module:
            knx_module.ui_time_server_controller.start(knx_module.xknx, config)
        await self._store.async_save(self.data)


class ConfigStoreException(Exception):
    """KNX config store exception."""
