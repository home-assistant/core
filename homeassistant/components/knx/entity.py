"""Base classes for KNX entities."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from xknx.devices import Device as XknxDevice
from xknx.telegram.address import DeviceGroupAddress, GroupAddress

from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import DOMAIN
from .storage.config_store import PlatformControllerBase
from .storage.const import CONF_DEVICE_INFO

if TYPE_CHECKING:
    from .knx_module import KNXModule


def _stable_group_address_repr(part: DeviceGroupAddress | None | int | str) -> str:
    """Render a unique_id part independent of `GroupAddress.address_format`."""
    if isinstance(part, GroupAddress):
        # Always LONG (main/middle/sub) derived from raw, so the representation
        # does not change when the global address format changes (e.g. on ETS
        # project import). This is bijective with raw, keeping ids unique.
        return (
            f"{(part.raw >> 11) & 0b11111}/{(part.raw >> 8) & 0b111}/{part.raw & 0xFF}"
        )
    # InternalGroupAddress is already format-independent; None renders as "None"
    return str(part)


def build_yaml_unique_id(
    *parts: DeviceGroupAddress | None | int | str,
) -> tuple[str, str]:
    """Return `(new_stable_id, legacy_id)` for a YAML entity.

    `new_stable_id` is independent of the global group address format. `legacy_id`
    matches the id produced before this fix (using the current global format) and is
    used to migrate registry entries of installations not using the 3-level style.
    """
    new_id = "_".join(_stable_group_address_repr(part) for part in parts)
    legacy_id = "_".join(str(part) for part in parts)
    return new_id, legacy_id


@callback
def async_migrate_yaml_unique_id(
    hass: HomeAssistant, platform: Platform, legacy_id: str, new_id: str
) -> None:
    """Migrate a YAML entity unique_id from the legacy format to the stable one."""
    # migration from unstable group address string parts added in 2026.8
    if legacy_id == new_id:
        return
    ent_reg = er.async_get(hass)
    if (entity_id := ent_reg.async_get_entity_id(platform, DOMAIN, legacy_id)) is None:
        return
    try:
        ent_reg.async_update_entity(entity_id, new_unique_id=new_id)
    except ValueError:
        # A stable-id entity already exists next to the legacy one - e.g. the
        # original entity was orphaned under the stable id when the pre-fix bug
        # registered the legacy entry. Keep the stable entry, drop the legacy one.
        ent_reg.async_remove(entity_id)


@dataclass(slots=True, frozen=True)
class KnxEntityIdentifier:
    """Class to identify KNX entities in KNX frontend."""

    platform: str
    unique_id: str
    ui: bool  # ui or yaml entity


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

    @override
    async def create_entity(self, unique_id: str, config: dict[str, Any]) -> None:
        """Add a new UI entity."""
        await self._entity_platform.async_add_entities(
            [self._entity_class(self._knx_module, unique_id, config)]
        )

    @override
    async def update_entity(
        self, entity_entry: RegistryEntry, config: dict[str, Any]
    ) -> None:
        """Update an existing UI entities configuration."""
        await self._entity_platform.async_remove_entity(entity_entry.entity_id)
        await self.create_entity(unique_id=entity_entry.unique_id, config=config)


class _KnxEntityBase(Entity):
    """Representation of a KNX entity."""

    _attr_should_poll = False

    _attr_unique_id: str
    _knx_module: KNXModule
    _device: XknxDevice

    _knx_entity_identifier: KnxEntityIdentifier | None = None

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._knx_module.connected

    async def async_update(self) -> None:
        """Request a state update from KNX bus."""
        await self._device.sync()

    def after_update_callback(self, device: XknxDevice) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Store register state change callback and start device object."""
        self._device.register_device_updated_cb(self.after_update_callback)
        self._device.xknx.devices.async_add(self._device)
        if uid := self.unique_id:
            self._knx_entity_identifier = KnxEntityIdentifier(
                platform=self.platform_data.domain,
                unique_id=uid,
                ui=isinstance(self, KnxUiEntity),
            )
            self._knx_module.add_to_group_address_entities(
                group_addresses=self._device.group_addresses(),
                identifier=self._knx_entity_identifier,
            )

        # super call needed to have methods of multi-inherited classes called
        # eg. for restoring state (like _KNXSwitch)
        await super().async_added_to_hass()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.unregister_device_updated_cb(self.after_update_callback)
        self._device.xknx.devices.async_remove(self._device)
        if self._knx_entity_identifier:
            self._knx_module.remove_from_group_address_entities(
                group_addresses=self._device.group_addresses(),
                identifier=self._knx_entity_identifier,
            )


class KnxYamlEntity(_KnxEntityBase):
    """Representation of a KNX entity configured from YAML."""

    def __init__(
        self,
        knx_module: KNXModule,
        unique_id: str,
        name: str,
        entity_category: EntityCategory | None,
    ) -> None:
        """Initialize the YAML entity."""
        self._knx_module = knx_module
        self._attr_name = name or None
        self._attr_unique_id = unique_id
        self._attr_entity_category = entity_category


class KnxUiEntity(_KnxEntityBase):
    """Representation of a KNX UI entity."""

    _attr_has_entity_name = True

    def __init__(
        self, knx_module: KNXModule, unique_id: str, entity_config: dict[str, Any]
    ) -> None:
        """Initialize the UI entity."""
        self._knx_module = knx_module

        self._attr_name = entity_config[CONF_NAME]
        self._attr_unique_id = unique_id
        if entity_category := entity_config.get(CONF_ENTITY_CATEGORY):
            self._attr_entity_category = EntityCategory(entity_category)
        if device_info := entity_config.get(CONF_DEVICE_INFO):
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_info)})
