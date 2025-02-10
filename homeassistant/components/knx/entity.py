"""Base class for KNX devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

from xknx.devices import Device as XknxDevice

from homeassistant.const import CONF_ENTITY_CATEGORY, EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import DOMAIN
from .schema_ui import PlatformConfigSchema
from .storage.config_store import PlatformControllerBase
from .storage.const import CONF_DEVICE_INFO

if TYPE_CHECKING:
    from .knx_module import KNXModule


class KnxUiEntityPlatformController(PlatformControllerBase):
    """Class to manage dynamic adding and reloading of UI entities."""

    def __init__(
        self,
        knx_module: KNXModule,
        entity_platform: EntityPlatform,
        entity_class: type[KnxUiEntity],
    ) -> None:
        """Initialize the UI platform."""
        self._knx_module = knx_module
        self._entity_platform = entity_platform
        self._entity_class = entity_class

    async def create_entity(self, unique_id: str, config: dict[str, Any]) -> None:
        """Add a new UI entity."""
        await self._entity_platform.async_add_entities(
            [self._entity_class(self._knx_module, unique_id, config)]
        )

    async def update_entity(
        self, entity_entry: RegistryEntry, config: dict[str, Any]
    ) -> None:
        """Update an existing UI entities configuration."""
        await self._entity_platform.async_remove_entity(entity_entry.entity_id)
        await self.create_entity(unique_id=entity_entry.unique_id, config=config)


class _KnxEntityBase(Entity):
    """Representation of a KNX entity."""

    _attr_should_poll = False
    _knx_module: KNXModule
    _device: XknxDevice

    @property
    def name(self) -> str:
        """Return the name of the KNX device."""
        return self._device.name or ""

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._knx_module.connected

    async def async_update(self) -> None:
        """Request a state update from KNX bus."""
        await self._device.sync()

    def after_update_callback(self, device: XknxDevice) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Store register state change callback and start device object."""
        self._device.register_device_updated_cb(self.after_update_callback)
        self._device.xknx.devices.async_add(self._device)
        # super call needed to have methods of multi-inherited classes called
        # eg. for restoring state (like _KNXSwitch)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.unregister_device_updated_cb(self.after_update_callback)
        self._device.xknx.devices.async_remove(self._device)


class KnxYamlEntity(_KnxEntityBase):
    """Representation of a KNX entity configured from YAML."""

    def __init__(self, knx_module: KNXModule, device: XknxDevice) -> None:
        """Initialize the YAML entity."""
        self._knx_module = knx_module
        self._device = device


class KnxUiEntity(_KnxEntityBase):
    """Representation of a KNX UI entity."""

    _attr_unique_id: str
    _attr_has_entity_name = True

    def __init__(
        self, knx_module: KNXModule, unique_id: str, entity_config: dict[str, Any]
    ) -> None:
        """Initialize the UI entity."""
        self._knx_module = knx_module
        self._attr_unique_id = unique_id
        if entity_category := entity_config.get(CONF_ENTITY_CATEGORY):
            self._attr_entity_category = EntityCategory(entity_category)
        if device_info := entity_config.get(CONF_DEVICE_INFO):
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_info)})


@dataclass
class EntityConfiguration(ABC):
    """Base class for all entity configuration classes.

    This abstract class acts as a bridge between different input formats (e.g., YAML
    or UI-based configurations) and the actual Home Assistant platform entities. Its
    purpose is to consolidate all the attributes required to create and manage these
    entities in a single, coherent configuration object.

    By defining a strict interface for schema validation and data handling, subclasses
    can remain independent of how the underlying data is provided. This ensures that
    changes to input sources (for example, changes of the UI data schema) do not
    break existing implementations. In turn, new platform entities can be created
    consistently, since the internal structure for each entity type are
    encapsulated within the configuration class itself.

    Required Methods:
        1. ``get_platform()``: Returns a platform identifier string.
        2. ``get_schema()``: Provides a Voluptuous-compatible schema object for
           validating the structure and types of incoming data.
        3. ``from_dict(data)``: Constructs an instance from a dictionary

    Optional:
        - ``to_dict()``: If reverse serialization is needed, subclasses should override
          this method to produce a schema-compliant dictionary representation of the
          current configuration state.
    """

    @classmethod
    @abstractmethod
    def get_platform(cls) -> str:
        """Return a unique identifier for the platform.

        Subclasses must implement this method to provide a string that identifies
        the platform  the configuration belongs to.

        Returns:
            str: The platform identifier.

        """

    @classmethod
    @abstractmethod
    def get_schema(cls) -> PlatformConfigSchema:
        """Retrieve a validation schema for this configuration.

        Subclasses must implement this method to return a Voluptuous-compatible schema
        that defines the rules, structure, and types for validating the configuration data.

        Returns:
            PlatformConfigSchema: The schema object for validating input data.

        """

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create an instance from a dictionary of validated data.

        Subclasses must implement this method to parse the provided dictionary
        (already validated against the class schema) and return a new instance of
        the configuration class.

        Args:
            data (dict[str, Any]): A dictionary of configuration values that comply
                with the schema returned by ``get_schema()``.

        Returns:
            Self: An initialized instance of the subclass.

        """

    def to_dict(self) -> dict[str, Any]:
        """Convert the current instance into a schema-compliant dictionary.

        While not abstract, subclasses should override this method if reverse
        serialization is required for their particular use case. When implemented,
        the resulting dictionary must align with the schema defined in
        ``get_schema()``.

        Returns:
            dict[str, Any]: A dictionary representation of the configuration,
            conforming to the class schema.

        """
        return {}


@runtime_checkable
class Persistable(Protocol):
    """Provides an interface for persisting configuration data in a config store.

    This protocol can be used to extend ``EntityConfiguration classes``, ensuring they
    can be persisted in the integration's internal config store by implementing
    consistent and schema-agnostic storage routines.

    The methods ``from_storage_dict`` and ``to_storage_dict`` ensure that data is stored
    and retrieved in a uniform and schema-independent format.

    Implementing classes must ensure that:

    1. ``from_storage_dict`` correctly reconstructs an instance from a dictionary.
    2. ``to_storage_dict`` provides a dictionary representation suitable for storage.
    3. The stored representation remains stable across versions to prevent breaking changes.
    """

    @classmethod
    def from_storage_dict(cls, data: dict[str, Any]) -> Self:
        """Create a new instance from a dictionary retrieved from storage.

        This method reconstructs an instance using the provided dictionary.
        Implementations must ensure that all required fields are correctly
        extracted and converted to the appropriate data types.

        Args:
            data (dict[str, Any]): A dictionary containing serialized configuration data.

        Returns:
            Self: An instance of the implementing class, populated with data from storage.

        """

    def to_storage_dict(self) -> dict[str, Any]:
        """Convert the current instance into a dictionary suitable for storage.

        This method serializes the instance into a format that can be stored persistently.
        Implementations must ensure that:

        - All necessary data is included.
        - The output format is stable across versions.
        - Data format remain consistent with ``from_storage_dict``.

        Returns:
            dict[str, Any]: A dictionary representation of the instance for persistent storage.

        """
