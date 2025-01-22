"""Base class for KNX devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, fields, is_dataclass
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar, cast

from xknx.devices import Device as XknxDevice

from homeassistant.const import CONF_ENTITY_CATEGORY, EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import DOMAIN
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
class BasePlatformConfiguration(ABC):
    """Abstract base class for platform configuration.

    This class defines the minimal interface for handling platform-specific configurations,
    including schema validation and deserialization. It provides a framework for converting
    data into a schema-compliant format and validating configurations against a predefined schema.

    The `to_dict` method, which performs reverse serialization (i.e., converting an instance
    back into a dictionary), is not marked as abstract because reverse serialization may not
    be required for all use cases. If reverse serialization is needed, subclasses must
    override and implement the `to_dict` method to ensure schema compliance.

    Subclasses are required to:
    - Provide a schema definition through `get_schema()`.
    - Implement the `from_dict` method for creating instances from schema-compliant dictionaries.

    Optional:
    - Override `to_dict` if reverse serialization is required for the specific use case.
    """

    @classmethod
    @abstractmethod
    def get_schema(cls) -> Any:
        """Retrieve a schema definition used for validation.

        Subclasses must provide a Voluptuous complatible schema object that defines
        the structure and validation rules for the configuration.

        Returns:
            Any: The schema object for validation.

        """

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        """Create an instance from a schema-compliant dictionary.

        This method is mandatory for all subclasses and should validate the input
        against the schema returned by `get_schema()`.

        Args:
            data (dict[str, Any]): A dictionary adhering to the schema.

        Returns:
            Any: An instance of the subclass.

        """

    def to_dict(self) -> dict[str, Any]:
        """Convert the instance into a dictionary conforming to the schema.

        This method performs reverse serialization, converting the instance into
        a schema-compliant dictionary. While not abstract, subclasses must override
        this method if reverse serialization is necessary for their use case.

        The default implementation uses `asdict` to serialize all dataclass fields.

        Returns:
            dict[str, Any]: A dictionary representation of the instance, aligned
            with the schema.

        """
        return {}


InstanceType = TypeVar("InstanceType", bound=object)


class StorageSerializationMixin(Generic[InstanceType], ABC):
    """Adds storage-based serialization/deserialization to a dataclass.

    This mixin provides two methods for converting between a dataclass
    instance and a dictionary suitable for persistence in storage.
    The target class must be a dataclass (i.e., support `fields(cls)`).
    """

    @classmethod
    def from_storage_dict(
        cls: type[InstanceType], data: dict[str, Any]
    ) -> InstanceType:
        """Instantiate the class from a storage-compatible dictionary.

        This method filters out any keys not matching the dataclass fields
        and then uses the remaining data to initialize an instance.

        Args:
            data (dict[str, Any]): A dictionary representing the object
                in storage format.

        Returns:
            InstanceType: A newly instantiated object of this class.

        """
        if is_dataclass(cls):
            field_names = {field.name for field in fields(cls)}
            filtered_data: dict[str, Any] = {
                key: value for key, value in data.items() if key in field_names
            }
            return cast(InstanceType, cls(**filtered_data))
        raise TypeError(f"{cls} is not a dataclass.")

    def to_storage_dict(self: InstanceType) -> dict[str, Any]:
        """Convert the current instance into a dictionary suitable for storage.

        Uses `asdict` to serialize all dataclass fields into a standard dictionary.

        Returns:
            dict[str, Any]: A dictionary representation of this instance
            suitable for storing in databases, files, etc.

        """
        if is_dataclass(self) and not isinstance(self, type):
            return asdict(self)
        raise TypeError(
            "to_storage_dict can only be used on dataclass instances, not types."
        )


class StorageSerialization(ABC):
    """Adds storage-based serialization/deserialization to a dataclass.

    This mixin provides two methods for converting between a dataclass
    instance and a dictionary suitable for persistence in storage.
    The target class must be a dataclass (i.e., support `fields(cls)`).
    """

    @classmethod
    @abstractmethod
    def from_storage_dict(cls, data: dict[str, Any]) -> Self:
        """Instantiate the class from a storage-compatible dictionary.

        This method filters out any keys not matching the dataclass fields
        and then uses the remaining data to initialize an instance.

        Args:
            data (dict[str, Any]): A dictionary representing the object
                in storage format.

        Returns:
            InstanceType: A newly instantiated object of this class.

        """

    def to_storage_dict(self) -> dict[str, Any]:
        """Convert the current instance into a dictionary suitable for storage.

        Uses `asdict` to serialize all dataclass fields into a standard dictionary.

        Returns:
            dict[str, Any]: A dictionary representation of this instance
            suitable for storing in databases, files, etc.

        """
        if is_dataclass(self):
            return cast(dict[str, Any], asdict(self))  # type: ignore[unreachable]
        raise TypeError(f"{self} is not a dataclass.")
