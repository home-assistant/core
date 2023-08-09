"""Support for esphome entities."""
from __future__ import annotations

from collections.abc import Callable
import functools
import math
from typing import (  # pylint: disable=unused-import
    Any,
    Generic,
    TypeVar,
    cast,
)

from aioesphomeapi import (
    EntityCategory as EsphomeEntityCategory,
    EntityInfo,
    EntityState,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .domain_data import DomainData

# Import config flow so that it's added to the registry
from .entry_data import RuntimeEntryData
from .enum_mapper import EsphomeEnumMapper

_R = TypeVar("_R")
_InfoT = TypeVar("_InfoT", bound=EntityInfo)
_EntityT = TypeVar("_EntityT", bound="EsphomeEntity[Any,Any]")
_StateT = TypeVar("_StateT", bound=EntityState)


async def platform_async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    *,
    info_type: type[_InfoT],
    entity_type: type[_EntityT],
    state_type: type[_StateT],
) -> None:
    """Set up an esphome platform.

    This method is in charge of receiving, distributing and storing
    info and state updates.
    """
    entry_data: RuntimeEntryData = DomainData.get(hass).get_entry_data(entry)
    entry_data.info[info_type] = {}
    entry_data.state.setdefault(state_type, {})
    platform = entity_platform.async_get_current_platform()

    @callback
    def async_list_entities(infos: list[EntityInfo]) -> None:
        """Update entities of this platform when entities are listed."""
        current_infos = entry_data.info[info_type]
        new_infos: dict[int, EntityInfo] = {}
        add_entities: list[_EntityT] = []

        for info in infos:
            if not current_infos.pop(info.key, None):
                # Create new entity
                entity = entity_type(entry_data, platform.domain, info, state_type)
                add_entities.append(entity)
            new_infos[info.key] = info

        # Anything still in current_infos is now gone
        if current_infos:
            hass.async_create_task(
                entry_data.async_remove_entities(current_infos.values())
            )

        # Then update the actual info
        entry_data.info[info_type] = new_infos

        if new_infos:
            entry_data.async_update_entity_infos(new_infos.values())

        if add_entities:
            # Add entities to Home Assistant
            async_add_entities(add_entities)

    entry_data.cleanup_callbacks.append(
        entry_data.async_register_static_info_callback(info_type, async_list_entities)
    )


def esphome_state_property(
    func: Callable[[_EntityT], _R]
) -> Callable[[_EntityT], _R | None]:
    """Wrap a state property of an esphome entity.

    This checks if the state object in the entity is set, and
    prevents writing NAN values to the Home Assistant state machine.
    """

    @functools.wraps(func)
    def _wrapper(self: _EntityT) -> _R | None:
        # pylint: disable-next=protected-access
        if not self._has_state:
            return None
        val = func(self)
        if isinstance(val, float) and not math.isfinite(val):
            # Home Assistant doesn't use NaN or inf values in state machine
            # (not JSON serializable)
            return None
        return val

    return _wrapper


ICON_SCHEMA = vol.Schema(cv.icon)


ENTITY_CATEGORIES: EsphomeEnumMapper[
    EsphomeEntityCategory, EntityCategory | None
] = EsphomeEnumMapper(
    {
        EsphomeEntityCategory.NONE: None,
        EsphomeEntityCategory.CONFIG: EntityCategory.CONFIG,
        EsphomeEntityCategory.DIAGNOSTIC: EntityCategory.DIAGNOSTIC,
    }
)


class EsphomeEntity(Entity, Generic[_InfoT, _StateT]):
    """Define a base esphome entity."""

    _attr_should_poll = False
    _static_info: _InfoT
    _state: _StateT
    _has_state: bool

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        domain: str,
        entity_info: EntityInfo,
        state_type: type[_StateT],
    ) -> None:
        """Initialize."""

        self._entry_data = entry_data
        self._on_entry_data_changed()
        self._key = entity_info.key
        self._state_type = state_type
        self._on_static_info_update(entity_info)
        assert entry_data.device_info is not None
        device_info = entry_data.device_info
        self._device_info = device_info
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)}
        )
        self._entry_id = entry_data.entry_id
        #
        # If `friendly_name` is set, we use the Friendly naming rules, if
        # `friendly_name` is not set we make an exception to the naming rules for
        # backwards compatibility and use the Legacy naming rules.
        #
        # Friendly naming
        # - Friendly name is prepended to entity names
        # - Device Name is prepended to entity ids
        # - Entity id is constructed from device name and object id
        #
        # Legacy naming
        # - Device name is not prepended to entity names
        # - Device name is not prepended to entity ids
        # - Entity id is constructed from entity name
        #
        if not device_info.friendly_name:
            return
        self._attr_has_entity_name = True
        self.entity_id = f"{domain}.{device_info.name}_{entity_info.object_id}"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        entry_data = self._entry_data
        hass = self.hass
        key = self._key

        self.async_on_remove(
            entry_data.async_register_key_static_info_remove_callback(
                self._static_info,
                functools.partial(self.async_remove, force_remove=True),
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                hass,
                entry_data.signal_device_updated,
                self._on_device_update,
            )
        )
        self.async_on_remove(
            entry_data.async_subscribe_state_update(
                self._state_type, key, self._on_state_update
            )
        )
        self.async_on_remove(
            entry_data.async_register_key_static_info_updated_callback(
                self._static_info, self._on_static_info_update
            )
        )
        self._update_state_from_entry_data()

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Save the static info for this entity when it changes.

        This method can be overridden in child classes to know
        when the static info changes.
        """
        static_info = cast(_InfoT, static_info)
        self._static_info = static_info
        self._attr_unique_id = static_info.unique_id
        self._attr_entity_registry_enabled_default = not static_info.disabled_by_default
        self._attr_name = static_info.name
        if entity_category := static_info.entity_category:
            self._attr_entity_category = ENTITY_CATEGORIES.from_esphome(entity_category)
        else:
            self._attr_entity_category = None
        if icon := static_info.icon:
            self._attr_icon = cast(str, ICON_SCHEMA(icon))
        else:
            self._attr_icon = None

    @callback
    def _update_state_from_entry_data(self) -> None:
        """Update state from entry data."""

        state = self._entry_data.state
        key = self._key
        state_type = self._state_type
        has_state = key in state[state_type]
        if has_state:
            self._state = cast(_StateT, state[state_type][key])
        self._has_state = has_state

    @callback
    def _on_state_update(self) -> None:
        """Call when state changed.

        Behavior can be changed in child classes
        """
        self._update_state_from_entry_data()
        self.async_write_ha_state()

    @callback
    def _on_entry_data_changed(self) -> None:
        entry_data = self._entry_data
        self._api_version = entry_data.api_version
        self._client = entry_data.client

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        self._on_entry_data_changed()
        if not self._entry_data.available:
            # Only write state if the device has gone unavailable
            # since _on_state_update will be called if the device
            # is available when the full state arrives
            # through the next entity state packet.
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        if self._device_info.has_deep_sleep:
            # During deep sleep the ESP will not be connectable (by design)
            # For these cases, show it as available
            return self._entry_data.expected_disconnect

        return self._entry_data.available


class EsphomeAssistEntity(Entity):
    """Define a base entity for Assist Pipeline entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry_data: RuntimeEntryData) -> None:
        """Initialize the binary sensor."""
        self._entry_data: RuntimeEntryData = entry_data
        assert entry_data.device_info is not None
        device_info = entry_data.device_info
        self._device_info = device_info
        self._attr_unique_id = (
            f"{device_info.mac_address}-{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)}
        )

    @callback
    def _update(self) -> None:
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._entry_data.async_subscribe_assist_pipeline_update(self._update)
        )
