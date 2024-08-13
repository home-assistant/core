"""Base class for KNX devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from xknx.devices import Device as XknxDevice

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.entity_registry import RegistryEntry

if TYPE_CHECKING:
    from . import KNXModule

from .storage.config_store import PlatformControllerBase


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
        return self._device.name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._knx_module.connected

    async def async_update(self) -> None:
        """Request a state update from KNX bus."""
        await self._device.sync()

    def after_update_callback(self, _device: XknxDevice) -> None:
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


class KnxUiEntity(_KnxEntityBase, ABC):
    """Representation of a KNX UI entity."""

    _attr_unique_id: str

    @abstractmethod
    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize the UI entity."""
