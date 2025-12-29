"""Support for esphome entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
import math
from typing import TYPE_CHECKING, Any, Concatenate, Generic, TypeVar, cast

from aioesphomeapi import (
    APIConnectionError,
    DeviceInfo as EsphomeDeviceInfo,
    EntityCategory as EsphomeEntityCategory,
    EntityInfo,
    EntityState,
)
import voluptuous as vol

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_platform,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

# Import config flow so that it's added to the registry
from .entry_data import (
    DeviceEntityKey,
    ESPHomeConfigEntry,
    RuntimeEntryData,
    build_device_unique_id,
)
from .enum_mapper import EsphomeEnumMapper

_LOGGER = logging.getLogger(__name__)

_InfoT = TypeVar("_InfoT", bound=EntityInfo)
_EntityT = TypeVar("_EntityT", bound="EsphomeEntity[Any,Any]")
_StateT = TypeVar("_StateT", bound=EntityState)


@callback
def async_static_info_updated(
    hass: HomeAssistant,
    entry_data: RuntimeEntryData,
    platform: entity_platform.EntityPlatform,
    async_add_entities: AddEntitiesCallback,
    info_type: type[_InfoT],
    entity_type: type[_EntityT],
    state_type: type[_StateT],
    infos: list[EntityInfo],
) -> None:
    """Update entities of this platform when entities are listed."""
    current_infos = entry_data.info[info_type]
    device_info = entry_data.device_info
    if TYPE_CHECKING:
        assert device_info is not None
    new_infos: dict[DeviceEntityKey, EntityInfo] = {}
    add_entities: list[_EntityT] = []

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    # Track info by (info.device_id, info.key) to properly handle entities
    # moving between devices and support sub-devices with overlapping keys
    for info in infos:
        info_key = (info.device_id, info.key)
        new_infos[info_key] = info

        # Try to find existing entity - first with current device_id
        old_info = current_infos.pop(info_key, None)

        # If not found, search for entity with same key but different device_id
        # This handles the case where entity moved between devices
        if not old_info:
            for existing_device_id, existing_key in list(current_infos):
                if existing_key == info.key:
                    # Found entity with same key but different device_id
                    old_info = current_infos.pop((existing_device_id, existing_key))
                    break

        # Create new entity if it doesn't exist
        if not old_info:
            entity = entity_type(entry_data, info, state_type)
            add_entities.append(entity)
            continue

        # Entity exists - check if device_id has changed
        if old_info.device_id == info.device_id:
            continue

        # Entity has switched devices, need to migrate unique_id and handle state subscriptions
        old_unique_id = build_device_unique_id(device_info.mac_address, old_info)
        entity_id = ent_reg.async_get_entity_id(platform.domain, DOMAIN, old_unique_id)

        # If entity not found in registry, re-add it
        # This happens when the device_id changed and the old device was deleted
        if entity_id is None:
            _LOGGER.info(
                "Entity with old unique_id %s not found in registry after device_id "
                "changed from %s to %s, re-adding entity",
                old_unique_id,
                old_info.device_id,
                info.device_id,
            )
            entity = entity_type(entry_data, info, state_type)
            add_entities.append(entity)
            continue

        updates: dict[str, Any] = {}
        new_unique_id = build_device_unique_id(device_info.mac_address, info)

        # Update unique_id if it changed
        if old_unique_id != new_unique_id:
            updates["new_unique_id"] = new_unique_id

        # Update device assignment in registry
        if info.device_id:
            # Entity now belongs to a sub device
            new_device = dev_reg.async_get_device(
                identifiers={(DOMAIN, f"{device_info.mac_address}_{info.device_id}")}
            )
        else:
            # Entity now belongs to the main device
            new_device = dev_reg.async_get_device(
                connections={(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)}
            )

        if new_device:
            updates["device_id"] = new_device.id

        # Apply all registry updates at once
        if updates:
            ent_reg.async_update_entity(entity_id, **updates)

        # IMPORTANT: The entity's device assignment in Home Assistant is only read when the entity
        # is first added. Updating the registry alone won't move the entity to the new device
        # in the UI. Additionally, the entity's state subscription is tied to the old device_id,
        # so it won't receive state updates for the new device_id.
        #
        # We must remove the old entity and re-add it to ensure:
        # 1. The entity appears under the correct device in the UI
        # 2. The entity's state subscription is updated to use the new device_id
        _LOGGER.debug(
            "Entity %s moving from device_id %s to %s",
            info.key,
            old_info.device_id,
            info.device_id,
        )

        # Signal the existing entity to remove itself
        # The entity is registered with the old device_id, so we signal with that
        entry_data.async_signal_entity_removal(info_type, old_info.device_id, info.key)

        # Create new entity with the new device_id
        add_entities.append(entity_type(entry_data, info, state_type))

    # Anything still in current_infos is now gone
    if current_infos:
        entry_data.async_remove_entities(
            hass, current_infos.values(), device_info.mac_address
        )

    # Then update the actual info
    entry_data.info[info_type] = new_infos

    if new_infos:
        entry_data.async_update_entity_infos(new_infos.values())

    if add_entities:
        # Add entities to Home Assistant
        async_add_entities(add_entities)


async def platform_async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
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
    entry_data = entry.runtime_data
    entry_data.info[info_type] = {}
    platform = entity_platform.async_get_current_platform()
    on_static_info_update = functools.partial(
        async_static_info_updated,
        hass,
        entry_data,
        platform,
        async_add_entities,
        info_type,
        entity_type,
        state_type,
    )
    entry_data.cleanup_callbacks.append(
        entry_data.async_register_static_info_callback(
            info_type,
            on_static_info_update,
        )
    )


def esphome_state_property[_R, _EntityT: EsphomeEntity[Any, Any]](
    func: Callable[[_EntityT], _R],
) -> Callable[[_EntityT], _R | None]:
    """Wrap a state property of an esphome entity.

    This checks if the state object in the entity is set
    and returns None if it is not set.
    """

    @functools.wraps(func)
    def _wrapper(self: _EntityT) -> _R | None:
        return func(self) if self._has_state else None

    return _wrapper


def async_esphome_state_property[_R, _EntityT: EsphomeEntity[Any, Any]](
    func: Callable[[_EntityT], Awaitable[_R | None]],
) -> Callable[[_EntityT], Coroutine[Any, Any, _R | None]]:
    """Wrap a state property of an esphome entity.

    This checks if the state object in the entity is set
    and returns None if it is not set.
    """

    @functools.wraps(func)
    async def _wrapper(self: _EntityT) -> _R | None:
        return await func(self) if self._has_state else None

    return _wrapper


def esphome_float_state_property[_EntityT: EsphomeEntity[Any, Any]](
    func: Callable[[_EntityT], float | None],
) -> Callable[[_EntityT], float | None]:
    """Wrap a state property of an esphome entity that returns a float.

    This checks if the state object in the entity is set, and returns
    None if its not set. If also prevents writing NAN values to the
    Home Assistant state machine.
    """

    @functools.wraps(func)
    def _wrapper(self: _EntityT) -> float | None:
        if not self._has_state:
            return None
        val = func(self)
        # Home Assistant doesn't use NaN or inf values in state machine
        # (not JSON serializable)
        return None if val is None or not math.isfinite(val) else val

    return _wrapper


def convert_api_error_ha_error[**_P, _R, _EntityT: EsphomeBaseEntity](
    func: Callable[Concatenate[_EntityT, _P], Awaitable[None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate ESPHome command calls that send commands/make changes to the device.

    A decorator that wraps the passed in function, catches APIConnectionError errors,
    and raises a HomeAssistant error instead.
    """

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            return await func(self, *args, **kwargs)
        except APIConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_communicating_with_device",
                translation_placeholders={
                    "device_name": self._device_info.name,
                    "error": str(error),
                },
            ) from error

    return handler


ICON_SCHEMA = vol.Schema(cv.icon)


ENTITY_CATEGORIES: EsphomeEnumMapper[EsphomeEntityCategory, EntityCategory | None] = (
    EsphomeEnumMapper(
        {
            EsphomeEntityCategory.NONE: None,
            EsphomeEntityCategory.CONFIG: EntityCategory.CONFIG,
            EsphomeEntityCategory.DIAGNOSTIC: EntityCategory.DIAGNOSTIC,
        }
    )
)


class EsphomeBaseEntity(Entity):
    """Define a base esphome entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _device_info: EsphomeDeviceInfo
    device_entry: dr.DeviceEntry


class EsphomeEntity(EsphomeBaseEntity, Generic[_InfoT, _StateT]):
    """Define an esphome entity."""

    _static_info: _InfoT
    _state: _StateT
    _has_state: bool = False
    unique_id: str

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        entity_info: EntityInfo,
        state_type: type[_StateT],
    ) -> None:
        """Initialize."""
        self._entry_data = entry_data
        self._states = cast(dict[int, _StateT], entry_data.state[state_type])
        assert entry_data.device_info is not None
        device_info = entry_data.device_info
        self._on_entry_data_changed()
        self._key = entity_info.key
        self._state_type = state_type
        self._on_static_info_update(entity_info)

        # Determine the device connection based on whether this entity belongs to a sub device
        if entity_info.device_id:
            # Entity belongs to a sub device
            self._attr_device_info = DeviceInfo(
                identifiers={
                    (DOMAIN, f"{device_info.mac_address}_{entity_info.device_id}")
                }
            )
        else:
            # Entity belongs to the main device
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)}
            )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        entry_data = self._entry_data
        self.async_on_remove(
            entry_data.async_subscribe_device_updated(
                self._on_device_update,
            )
        )
        self.async_on_remove(
            entry_data.async_subscribe_state_update(
                self._static_info.device_id,
                self._state_type,
                self._key,
                self._on_state_update,
            )
        )
        self.async_on_remove(
            entry_data.async_register_key_static_info_updated_callback(
                self._static_info, self._on_static_info_update
            )
        )
        # Register to be notified when this entity should remove itself
        # This happens when the entity moves to a different device
        self.async_on_remove(
            entry_data.async_register_entity_removal_callback(
                type(self._static_info),
                self._static_info.device_id,
                self._key,
                self._on_removal_signal,
            )
        )
        self._update_state_from_entry_data()

    @callback
    def _on_removal_signal(self) -> None:
        """Handle signal to remove this entity."""
        _LOGGER.debug(
            "Entity %s received removal signal due to device_id change",
            self.entity_id,
        )
        # Schedule the entity to be removed
        # This must be done as a task since we're in a callback
        self.hass.async_create_task(self.async_remove())

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Save the static info for this entity when it changes.

        This method can be overridden in child classes to know
        when the static info changes.
        """
        device_info = self._entry_data.device_info
        if TYPE_CHECKING:
            static_info = cast(_InfoT, static_info)
            assert device_info
        self._static_info = static_info
        self._attr_unique_id = build_device_unique_id(
            device_info.mac_address, static_info
        )
        self._attr_entity_registry_enabled_default = not static_info.disabled_by_default
        # https://github.com/home-assistant/core/issues/132532
        # If the name is "", we need to set it to None since otherwise
        # the friendly_name will be "{friendly_name} " with a trailing
        # space. ESPHome uses protobuf under the hood, and an empty field
        # gets a default value of "".
        self._attr_name = static_info.name if static_info.name else None
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
        key = self._key
        if has_state := key in self._states:
            self._state = self._states[key]
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
        # Update the device info since it can change
        # when the device is reconnected
        if TYPE_CHECKING:
            assert entry_data.device_info is not None
        self._device_info = entry_data.device_info
        self._api_version = entry_data.api_version
        self._client = entry_data.client
        if self._device_info.has_deep_sleep:
            # During deep sleep the ESP will not be connectable (by design)
            # For these cases, show it as available
            self._attr_available = entry_data.expected_disconnect
        else:
            self._attr_available = entry_data.available

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


class EsphomeAssistEntity(EsphomeBaseEntity):
    """Define a base entity for Assist Pipeline entities."""

    def __init__(self, entry_data: RuntimeEntryData) -> None:
        """Initialize the binary sensor."""
        self._entry_data = entry_data
        assert entry_data.device_info is not None
        device_info = entry_data.device_info
        self._device_info = device_info
        self._attr_unique_id = (
            f"{device_info.mac_address}-{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)}
        )

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._entry_data.async_subscribe_assist_pipeline_update(
                self.async_write_ha_state
            )
        )
