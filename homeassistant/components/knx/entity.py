"""Base classes for KNX entities."""

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, override

from xknx.devices import Device as XknxDevice
from xknx.telegram.address import DeviceGroupAddress, GroupAddress

from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    CONF_DEVICE,
    CONF_ENTITY_CATEGORY,
    CONF_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import (
    EntityPlatform,
    async_get_current_platform,
)
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import CONF_DEFAULT_ENTITY_ID, DOMAIN
from .storage.config_store import PlatformControllerBase
from .storage.const import CONF_DEVICE_INFO

if TYPE_CHECKING:
    from .knx_module import KNXModule

_LOGGER = logging.getLogger(__name__)


def _stable_group_address_repr(part: DeviceGroupAddress | int | str | None) -> str:
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
    *parts: DeviceGroupAddress | int | str | None,
) -> tuple[str, str]:
    """Return `(new_stable_id, legacy_id)` for a YAML entity.

    `new_stable_id` is independent of the global group address format. `legacy_id`
    matches the id produced before this fix (using the current global format) and is
    used to migrate registry entries of installations not using the 3-level style.
    Pass the result as `unique_id` to `KnxYamlEntity`, which runs the migration.
    """
    new_id = "_".join(_stable_group_address_repr(part) for part in parts)
    legacy_id = "_".join(str(part) for part in parts)
    return new_id, legacy_id


@callback
def async_migrate_yaml_unique_id(
    hass: HomeAssistant, platform: str, legacy_id: str, new_id: str
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

    # `assumed_state` toggles when a restored state is confirmed by the bus,
    # which would otherwise write a new attributes row for every entity on startup
    _unrecorded_attributes = frozenset({ATTR_ASSUMED_STATE})
    _attr_has_entity_name = True
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
        unique_id: tuple[str, str],  # new_stable_id, legacy_id for migration
        entity_config: dict[str, Any],
    ) -> None:
        """Initialize the YAML entity.

        `unique_id` is the `(new_stable_id, legacy_id)` tuple from
        `build_yaml_unique_id`; the legacy id is migrated to the stable one. A
        user-defined `unique_id` in the config takes precedence, and an existing
        auto-generated entity is migrated to it so history is preserved. Removing
        a user-defined `unique_id` again cannot be migrated back. If the id is
        already used by another entity, the generated id is kept instead.
        """
        new_unique_id, legacy_unique_id = unique_id
        platform = async_get_current_platform().domain
        async_migrate_yaml_unique_id(
            knx_module.hass, platform, legacy_unique_id, new_unique_id
        )
        if (user_unique_id := entity_config.get(CONF_UNIQUE_ID)) and (
            user_unique_id != new_unique_id
        ):
            ent_reg = er.async_get(knx_module.hass)
            generated_entity_id = ent_reg.async_get_entity_id(
                platform, DOMAIN, new_unique_id
            )
            if generated_entity_id is None:
                # new entity, or already migrated on an earlier run
                new_unique_id = user_unique_id
            else:
                try:
                    # rename the existing entry, preserving history and settings
                    ent_reg.async_update_entity(
                        generated_entity_id, new_unique_id=user_unique_id
                    )
                except ValueError:
                    # id already belongs to another entity - keep the generated one
                    _LOGGER.warning(
                        "Configured `unique_id: %s` for %s entity '%s' is already"
                        " in use; keeping the generated unique id instead",
                        user_unique_id,
                        platform,
                        entity_config[CONF_NAME],
                    )
                else:
                    new_unique_id = user_unique_id
        self._knx_module = knx_module
        self._attr_name = entity_config[CONF_NAME] or None
        self._attr_unique_id = new_unique_id
        self._attr_entity_category = entity_config.get(CONF_ENTITY_CATEGORY)

        if device := entity_config.get(CONF_DEVICE):
            # Entities sharing the same `device` `id` are grouped into one
            # device. `id` is normalized in the schema (`_device_id`), which
            # also lets YAML entities join a UI-created device by referencing
            # its identifier verbatim.
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device[CONF_ID])},
                manufacturer="KNX",
            )
            if device_name := device.get(CONF_NAME):
                self._attr_device_info["name"] = device_name

        default_entity_id: str | None
        if (default_entity_id := entity_config.get(CONF_DEFAULT_ENTITY_ID)) is not None:
            self.entity_id = default_entity_id


class KnxUiEntity(_KnxEntityBase):
    """Representation of a KNX UI entity."""

    def __init__(
        self, knx_module: KNXModule, unique_id: str, entity_config: dict[str, Any]
    ) -> None:
        """Initialize the UI entity."""
        self._knx_module = knx_module

        self._attr_name = entity_config[CONF_NAME]
        self._attr_unique_id = unique_id
        self._attr_entity_category = entity_config[CONF_ENTITY_CATEGORY]
        if device_info := entity_config[CONF_DEVICE_INFO]:
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_info)})
