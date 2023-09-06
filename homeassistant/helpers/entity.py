"""An abstract class for entities."""
from __future__ import annotations

from abc import ABC
import asyncio
from collections.abc import Coroutine, Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
import functools as ft
import logging
import math
import sys
from timeit import default_timer as timer
from typing import TYPE_CHECKING, Any, Final, Literal, TypeVar, final

import voluptuous as vol

from homeassistant.backports.functools import cached_property
from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_DEFAULT_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import (
    HomeAssistantError,
    InvalidStateError,
    NoEntitySpecifiedError,
)
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util, ensure_unique_string, slugify

from . import device_registry as dr, entity_registry as er
from .device_registry import DeviceInfo, EventDeviceRegistryUpdatedData
from .event import (
    async_track_device_registry_updated_event,
    async_track_entity_registry_updated_event,
)
from .typing import UNDEFINED, EventType, StateType, UndefinedType

if TYPE_CHECKING:
    from .entity_platform import EntityPlatform


_T = TypeVar("_T")

_LOGGER = logging.getLogger(__name__)
SLOW_UPDATE_WARNING = 10
DATA_ENTITY_SOURCE = "entity_info"
SOURCE_CONFIG_ENTRY = "config_entry"
SOURCE_PLATFORM_CONFIG = "platform_config"

# Used when converting float states to string: limit precision according to machine
# epsilon to make the string representation readable
FLOAT_PRECISION = abs(int(math.floor(math.log10(abs(sys.float_info.epsilon))))) - 1


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up entity sources."""
    hass.data[DATA_ENTITY_SOURCE] = {}


@callback
@bind_hass
def entity_sources(hass: HomeAssistant) -> dict[str, dict[str, str]]:
    """Get the entity sources."""
    _entity_sources: dict[str, dict[str, str]] = hass.data[DATA_ENTITY_SOURCE]
    return _entity_sources


def generate_entity_id(
    entity_id_format: str,
    name: str | None,
    current_ids: list[str] | None = None,
    hass: HomeAssistant | None = None,
) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    return async_generate_entity_id(entity_id_format, name, current_ids, hass)


@callback
def async_generate_entity_id(
    entity_id_format: str,
    name: str | None,
    current_ids: Iterable[str] | None = None,
    hass: HomeAssistant | None = None,
) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    name = (name or DEVICE_DEFAULT_NAME).lower()
    preferred_string = entity_id_format.format(slugify(name))

    if current_ids is not None:
        return ensure_unique_string(preferred_string, current_ids)

    if hass is None:
        raise ValueError("Missing required parameter current_ids or hass")

    test_string = preferred_string
    tries = 1
    while not hass.states.async_available(test_string):
        tries += 1
        test_string = f"{preferred_string}_{tries}"

    return test_string


def get_capability(hass: HomeAssistant, entity_id: str, capability: str) -> Any | None:
    """Get a capability attribute of an entity.

    First try the statemachine, then entity registry.
    """
    if state := hass.states.get(entity_id):
        return state.attributes.get(capability)

    entity_registry = er.async_get(hass)
    if not (entry := entity_registry.async_get(entity_id)):
        raise HomeAssistantError(f"Unknown entity {entity_id}")

    return entry.capabilities.get(capability) if entry.capabilities else None


def get_device_class(hass: HomeAssistant, entity_id: str) -> str | None:
    """Get device class of an entity.

    First try the statemachine, then entity registry.
    """
    if state := hass.states.get(entity_id):
        return state.attributes.get(ATTR_DEVICE_CLASS)

    entity_registry = er.async_get(hass)
    if not (entry := entity_registry.async_get(entity_id)):
        raise HomeAssistantError(f"Unknown entity {entity_id}")

    return entry.device_class or entry.original_device_class


def get_supported_features(hass: HomeAssistant, entity_id: str) -> int:
    """Get supported features for an entity.

    First try the statemachine, then entity registry.
    """
    if state := hass.states.get(entity_id):
        return state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

    entity_registry = er.async_get(hass)
    if not (entry := entity_registry.async_get(entity_id)):
        raise HomeAssistantError(f"Unknown entity {entity_id}")

    return entry.supported_features or 0


def get_unit_of_measurement(hass: HomeAssistant, entity_id: str) -> str | None:
    """Get unit of measurement of an entity.

    First try the statemachine, then entity registry.
    """
    if state := hass.states.get(entity_id):
        return state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

    entity_registry = er.async_get(hass)
    if not (entry := entity_registry.async_get(entity_id)):
        raise HomeAssistantError(f"Unknown entity {entity_id}")

    return entry.unit_of_measurement


ENTITY_CATEGORIES_SCHEMA: Final = vol.Coerce(EntityCategory)


class EntityPlatformState(Enum):
    """The platform state of an entity."""

    # Not Added: Not yet added to a platform, polling updates
    # are written to the state machine.
    NOT_ADDED = auto()

    # Added: Added to a platform, polling updates
    # are written to the state machine.
    ADDED = auto()

    # Removed: Removed from a platform, polling updates
    # are not written to the state machine.
    REMOVED = auto()


@dataclass(slots=True)
class EntityDescription:
    """A class that describes Home Assistant entities."""

    # This is the key identifier for this entity
    key: str

    device_class: str | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True
    force_update: bool = False
    icon: str | None = None
    has_entity_name: bool = False
    name: str | UndefinedType | None = UNDEFINED
    translation_key: str | None = None
    unit_of_measurement: str | None = None


class Entity(ABC):
    """An abstract class for Home Assistant entities."""

    # SAFE TO OVERWRITE
    # The properties and methods here are safe to overwrite when inheriting
    # this class. These may be used to customize the behavior of the entity.
    entity_id: str = None  # type: ignore[assignment]

    # Owning hass instance. Set by EntityPlatform by calling add_to_platform_start
    # While not purely typed, it makes typehinting more useful for us
    # and removes the need for constant None checks or asserts.
    hass: HomeAssistant = None  # type: ignore[assignment]

    # Owning platform instance. Set by EntityPlatform by calling add_to_platform_start
    # While not purely typed, it makes typehinting more useful for us
    # and removes the need for constant None checks or asserts.
    platform: EntityPlatform = None  # type: ignore[assignment]

    # Entity description instance for this Entity
    entity_description: EntityDescription

    # If we reported if this entity was slow
    _slow_reported = False

    # If we reported this entity is updated while disabled
    _disabled_reported = False

    # If we reported this entity is using async_update_ha_state, while
    # it should be using async_write_ha_state.
    _async_update_ha_state_reported = False

    # If we reported this entity is implicitly using device name
    _implicit_device_name_reported = False

    # If we reported this entity was added without its platform set
    _no_platform_reported = False

    # Protect for multiple updates
    _update_staged = False

    # Process updates in parallel
    parallel_updates: asyncio.Semaphore | None = None

    # Entry in the entity registry
    registry_entry: er.RegistryEntry | None = None

    # The device entry for this entity
    device_entry: dr.DeviceEntry | None = None

    # Hold list for functions to call on remove.
    _on_remove: list[CALLBACK_TYPE] | None = None

    _unsub_device_updates: CALLBACK_TYPE | None = None

    # Context
    _context: Context | None = None
    _context_set: datetime | None = None

    # If entity is added to an entity platform
    _platform_state = EntityPlatformState.NOT_ADDED

    # Entity Properties
    _attr_assumed_state: bool = False
    _attr_attribution: str | None = None
    _attr_available: bool = True
    _attr_capability_attributes: Mapping[str, Any] | None = None
    _attr_context_recent_time: timedelta = timedelta(seconds=5)
    _attr_device_class: str | None
    _attr_device_info: DeviceInfo | None = None
    _attr_entity_category: EntityCategory | None
    _attr_has_entity_name: bool
    _attr_entity_picture: str | None = None
    _attr_entity_registry_enabled_default: bool
    _attr_entity_registry_visible_default: bool
    _attr_extra_state_attributes: MutableMapping[str, Any]
    _attr_force_update: bool
    _attr_icon: str | None
    _attr_name: str | None
    _attr_should_poll: bool = True
    _attr_state: StateType = STATE_UNKNOWN
    _attr_supported_features: int | None = None
    _attr_translation_key: str | None
    _attr_unique_id: str | None = None
    _attr_unit_of_measurement: str | None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return self._attr_should_poll

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._attr_unique_id

    def _report_implicit_device_name(self) -> None:
        """Report entities which use implicit device name."""
        if self._implicit_device_name_reported:
            return
        report_issue = self._suggest_report_issue()
        _LOGGER.warning(
            (
                "Entity %s (%s) is implicitly using device name by not setting its "
                "name. Instead, the name should be set to None, please %s"
            ),
            self.entity_id,
            type(self),
            report_issue,
        )
        self._implicit_device_name_reported = True

    @property
    def use_device_name(self) -> bool:
        """Return if this entity does not have its own name.

        Should be True if the entity represents the single main feature of a device.
        """
        if hasattr(self, "_attr_name"):
            return not self._attr_name

        if name_translation_key := self._name_translation_key:
            if name_translation_key in self.platform.platform_translations:
                return False

        if hasattr(self, "entity_description"):
            if not (name := self.entity_description.name):
                return True
            if name is UNDEFINED and not self._default_to_device_class_name():
                # Backwards compatibility with leaving EntityDescription.name unassigned
                # for device name.
                # Deprecated in HA Core 2023.6, remove in HA Core 2023.9
                self._report_implicit_device_name()
                return True
            return False
        if self.name is UNDEFINED and not self._default_to_device_class_name():
            # Backwards compatibility with not overriding name property for device name.
            # Deprecated in HA Core 2023.6, remove in HA Core 2023.9
            self._report_implicit_device_name()
            return True
        return not self.name

    @property
    def has_entity_name(self) -> bool:
        """Return if the name of the entity is describing only the entity itself."""
        if hasattr(self, "_attr_has_entity_name"):
            return self._attr_has_entity_name
        if hasattr(self, "entity_description"):
            return self.entity_description.has_entity_name
        return False

    def _device_class_name_helper(
        self,
        component_translations: dict[str, Any],
    ) -> str | None:
        """Return a translated name of the entity based on its device class."""
        if not self.has_entity_name:
            return None
        device_class_key = self.device_class or "_"
        platform = self.platform
        name_translation_key = (
            f"component.{platform.domain}.entity_component.{device_class_key}.name"
        )
        return component_translations.get(name_translation_key)

    @cached_property
    def _object_id_device_class_name(self) -> str | None:
        """Return a translated name of the entity based on its device class."""
        return self._device_class_name_helper(
            self.platform.object_id_component_translations
        )

    @cached_property
    def _device_class_name(self) -> str | None:
        """Return a translated name of the entity based on its device class."""
        return self._device_class_name_helper(self.platform.component_translations)

    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class."""
        return False

    @cached_property
    def _name_translation_key(self) -> str | None:
        """Return translation key for entity name."""
        if self.translation_key is None:
            return None
        platform = self.platform
        return (
            f"component.{platform.platform_name}.entity.{platform.domain}"
            f".{self.translation_key}.name"
        )

    def _name_internal(
        self,
        device_class_name: str | None,
        platform_translations: dict[str, Any],
    ) -> str | UndefinedType | None:
        """Return the name of the entity."""
        if hasattr(self, "_attr_name"):
            return self._attr_name
        if (
            self.has_entity_name
            and (name_translation_key := self._name_translation_key)
            and (name := platform_translations.get(name_translation_key))
        ):
            if TYPE_CHECKING:
                assert isinstance(name, str)
            return name
        if hasattr(self, "entity_description"):
            description_name = self.entity_description.name
            if description_name is UNDEFINED and self._default_to_device_class_name():
                return device_class_name
            return description_name

        # The entity has no name set by _attr_name, translation_key or entity_description
        # Check if the entity should be named by its device class
        if self._default_to_device_class_name():
            return device_class_name
        return UNDEFINED

    @property
    def suggested_object_id(self) -> str | None:
        """Return input for object id."""
        # The check for self.platform guards against integrations not using an
        # EntityComponent and can be removed in HA Core 2024.1
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        if self.__class__.name.fget is Entity.name.fget and self.platform:  # type: ignore[attr-defined]
            name = self._name_internal(
                self._object_id_device_class_name,
                self.platform.object_id_platform_translations,
            )
        else:
            name = self.name
        return None if name is UNDEFINED else name

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""
        # The check for self.platform guards against integrations not using an
        # EntityComponent and can be removed in HA Core 2024.1
        if not self.platform:
            return self._name_internal(None, {})
        return self._name_internal(
            self._device_class_name,
            self.platform.platform_translations,
        )

    @property
    def state(self) -> StateType:
        """Return the state of the entity."""
        return self._attr_state

    @property
    def capability_attributes(self) -> Mapping[str, Any] | None:
        """Return the capability attributes.

        Attributes that explain the capabilities of an entity.

        Implemented by component base class. Convention for attribute names
        is lowercase snake_case.
        """
        return self._attr_capability_attributes

    def get_initial_entity_options(self) -> er.EntityOptionsType | None:
        """Return initial entity options.

        These will be stored in the entity registry the first time the entity is seen,
        and then never updated.

        Implemented by component base class, should not be extended by integrations.

        Note: Not a property to avoid calculating unless needed.
        """
        return None

    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes.

        Implemented by component base class, should not be extended by integrations.
        Convention for attribute names is lowercase snake_case.
        """
        return None

    @property
    def device_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes.

        This method is deprecated, platform classes should implement
        extra_state_attributes instead.
        """
        return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        if hasattr(self, "_attr_extra_state_attributes"):
            return self._attr_extra_state_attributes
        return None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return self._attr_device_info

    @property
    def device_class(self) -> str | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity, if any."""
        if hasattr(self, "_attr_unit_of_measurement"):
            return self._attr_unit_of_measurement
        if hasattr(self, "entity_description"):
            return self.entity_description.unit_of_measurement
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if hasattr(self, "_attr_icon"):
            return self._attr_icon
        if hasattr(self, "entity_description"):
            return self.entity_description.icon
        return None

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        return self._attr_entity_picture

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return self._attr_assumed_state

    @property
    def force_update(self) -> bool:
        """Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        if hasattr(self, "_attr_force_update"):
            return self._attr_force_update
        if hasattr(self, "entity_description"):
            return self.entity_description.force_update
        return False

    @property
    def supported_features(self) -> int | None:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def context_recent_time(self) -> timedelta:
        """Time that a context is considered recent."""
        return self._attr_context_recent_time

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added.

        This only applies when fist added to the entity registry.
        """
        if hasattr(self, "_attr_entity_registry_enabled_default"):
            return self._attr_entity_registry_enabled_default
        if hasattr(self, "entity_description"):
            return self.entity_description.entity_registry_enabled_default
        return True

    @property
    def entity_registry_visible_default(self) -> bool:
        """Return if the entity should be visible when first added.

        This only applies when fist added to the entity registry.
        """
        if hasattr(self, "_attr_entity_registry_visible_default"):
            return self._attr_entity_registry_visible_default
        if hasattr(self, "entity_description"):
            return self.entity_description.entity_registry_visible_default
        return True

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        return self._attr_attribution

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the category of the entity, if any."""
        if hasattr(self, "_attr_entity_category"):
            return self._attr_entity_category
        if hasattr(self, "entity_description"):
            return self.entity_description.entity_category
        return None

    @property
    def translation_key(self) -> str | None:
        """Return the translation key to translate the entity's states."""
        if hasattr(self, "_attr_translation_key"):
            return self._attr_translation_key
        if hasattr(self, "entity_description"):
            return self.entity_description.translation_key
        return None

    # DO NOT OVERWRITE
    # These properties and methods are either managed by Home Assistant or they
    # are used to perform a very specific function. Overwriting these may
    # produce undesirable effects in the entity's operation.

    @property
    def enabled(self) -> bool:
        """Return if the entity is enabled in the entity registry.

        If an entity is not part of the registry, it cannot be disabled
        and will therefore always be enabled.
        """
        return self.registry_entry is None or not self.registry_entry.disabled

    @callback
    def async_set_context(self, context: Context) -> None:
        """Set the context the entity currently operates under."""
        self._context = context
        self._context_set = dt_util.utcnow()

    async def async_update_ha_state(self, force_refresh: bool = False) -> None:
        """Update Home Assistant with current state of entity.

        If force_refresh == True will update entity before setting state.

        This method must be run in the event loop.
        """
        if self.hass is None:
            raise RuntimeError(f"Attribute hass is None for {self}")

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                f"No entity id specified for entity {self.name}"
            )

        # update entity data
        if force_refresh:
            try:
                await self.async_device_update()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Update for %s fails", self.entity_id)
                return
        elif not self._async_update_ha_state_reported:
            report_issue = self._suggest_report_issue()
            _LOGGER.warning(
                (
                    "Entity %s (%s) is using self.async_update_ha_state(), without"
                    " enabling force_update. Instead it should use"
                    " self.async_write_ha_state(), please %s"
                ),
                self.entity_id,
                type(self),
                report_issue,
            )
            self._async_update_ha_state_reported = True

        self._async_write_ha_state()

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        if self.hass is None:
            raise RuntimeError(f"Attribute hass is None for {self}")

        # The check for self.platform guards against integrations not using an
        # EntityComponent and can be removed in HA Core 2024.1
        if self.platform is None and not self._no_platform_reported:  # type: ignore[unreachable]
            report_issue = self._suggest_report_issue()  # type: ignore[unreachable]
            _LOGGER.warning(
                (
                    "Entity %s (%s) does not have a platform, this may be caused by "
                    "adding it manually instead of with an EntityComponent helper"
                    ", please %s"
                ),
                self.entity_id,
                type(self),
                report_issue,
            )
            self._no_platform_reported = True

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                f"No entity id specified for entity {self.name}"
            )

        self._async_write_ha_state()

    def _stringify_state(self, available: bool) -> str:
        """Convert state to string."""
        if not available:
            return STATE_UNAVAILABLE
        if (state := self.state) is None:
            return STATE_UNKNOWN
        if isinstance(state, float):
            # If the entity's state is a float, limit precision according to machine
            # epsilon to make the string representation readable
            return f"{state:.{FLOAT_PRECISION}}"
        return str(state)

    def _friendly_name_internal(self) -> str | None:
        """Return the friendly name.

        If has_entity_name is False, this returns self.name
        If has_entity_name is True, this returns device.name + self.name
        """
        name = self.name
        if name is UNDEFINED:
            name = None

        if not self.has_entity_name or not (device_entry := self.device_entry):
            return name

        device_name = device_entry.name_by_user or device_entry.name
        if self.use_device_name:
            return device_name
        return f"{device_name} {name}" if device_name else name

    @callback
    def _async_generate_attributes(self) -> tuple[str, dict[str, Any]]:
        """Calculate state string and attribute mapping."""
        entry = self.registry_entry

        attr = self.capability_attributes
        attr = dict(attr) if attr else {}

        available = self.available  # only call self.available once per update cycle
        state = self._stringify_state(available)
        if available:
            attr.update(self.state_attributes or {})
            attr.update(self.extra_state_attributes or {})

        if (unit_of_measurement := self.unit_of_measurement) is not None:
            attr[ATTR_UNIT_OF_MEASUREMENT] = unit_of_measurement

        if assumed_state := self.assumed_state:
            attr[ATTR_ASSUMED_STATE] = assumed_state

        if (attribution := self.attribution) is not None:
            attr[ATTR_ATTRIBUTION] = attribution

        if (
            device_class := (entry and entry.device_class) or self.device_class
        ) is not None:
            attr[ATTR_DEVICE_CLASS] = str(device_class)

        if (entity_picture := self.entity_picture) is not None:
            attr[ATTR_ENTITY_PICTURE] = entity_picture

        if (icon := (entry and entry.icon) or self.icon) is not None:
            attr[ATTR_ICON] = icon

        if (
            name := (entry and entry.name) or self._friendly_name_internal()
        ) is not None:
            attr[ATTR_FRIENDLY_NAME] = name

        if (supported_features := self.supported_features) is not None:
            attr[ATTR_SUPPORTED_FEATURES] = supported_features

        return (state, attr)

    @callback
    def _async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        if self._platform_state == EntityPlatformState.REMOVED:
            # Polling returned after the entity has already been removed
            return

        hass = self.hass
        entity_id = self.entity_id

        if (entry := self.registry_entry) and entry.disabled_by:
            if not self._disabled_reported:
                self._disabled_reported = True
                _LOGGER.warning(
                    (
                        "Entity %s is incorrectly being triggered for updates while it"
                        " is disabled. This is a bug in the %s integration"
                    ),
                    entity_id,
                    self.platform.platform_name,
                )
            return

        start = timer()
        state, attr = self._async_generate_attributes()
        end = timer()

        if end - start > 0.4 and not self._slow_reported:
            self._slow_reported = True
            report_issue = self._suggest_report_issue()
            _LOGGER.warning(
                "Updating state for %s (%s) took %.3f seconds. Please %s",
                entity_id,
                type(self),
                end - start,
                report_issue,
            )

        # Overwrite properties that have been set in the config file.
        if customize := hass.data.get(DATA_CUSTOMIZE):
            attr.update(customize.get(entity_id))

        if (
            self._context_set is not None
            and dt_util.utcnow() - self._context_set > self.context_recent_time
        ):
            self._context = None
            self._context_set = None

        try:
            hass.states.async_set(
                entity_id, state, attr, self.force_update, self._context
            )
        except InvalidStateError:
            _LOGGER.exception("Failed to set state, fall back to %s", STATE_UNKNOWN)
            hass.states.async_set(
                entity_id, STATE_UNKNOWN, {}, self.force_update, self._context
            )

    def schedule_update_ha_state(self, force_refresh: bool = False) -> None:
        """Schedule an update ha state change task.

        Scheduling the update avoids executor deadlocks.

        Entity state and attributes are read when the update ha state change
        task is executed.
        If state is changed more than once before the ha state change task has
        been executed, the intermediate state transitions will be missed.
        """
        if force_refresh:
            self.hass.create_task(
                self.async_update_ha_state(force_refresh),
                f"Entity {self.entity_id} schedule update ha state",
            )
        else:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    @callback
    def async_schedule_update_ha_state(self, force_refresh: bool = False) -> None:
        """Schedule an update ha state change task.

        This method must be run in the event loop.
        Scheduling the update avoids executor deadlocks.

        Entity state and attributes are read when the update ha state change
        task is executed.
        If state is changed more than once before the ha state change task has
        been executed, the intermediate state transitions will be missed.
        """
        if force_refresh:
            self.hass.async_create_task(
                self.async_update_ha_state(force_refresh),
                f"Entity schedule update ha state {self.entity_id}",
            )
        else:
            self.async_write_ha_state()

    @callback
    def _async_slow_update_warning(self) -> None:
        """Log a warning if update is taking too long."""
        _LOGGER.warning(
            "Update of %s is taking over %s seconds",
            self.entity_id,
            SLOW_UPDATE_WARNING,
        )

    async def async_device_update(self, warning: bool = True) -> None:
        """Process 'update' or 'async_update' from entity.

        This method is a coroutine.
        """
        if self._update_staged:
            return

        hass = self.hass
        assert hass is not None

        self._update_staged = True

        # Process update sequential
        if self.parallel_updates:
            await self.parallel_updates.acquire()

        if warning:
            update_warn = hass.loop.call_at(
                hass.loop.time() + SLOW_UPDATE_WARNING, self._async_slow_update_warning
            )

        try:
            if hasattr(self, "async_update"):
                await self.async_update()
            elif hasattr(self, "update"):
                await hass.async_add_executor_job(self.update)
            else:
                return
        finally:
            self._update_staged = False
            if warning:
                update_warn.cancel()
            if self.parallel_updates:
                self.parallel_updates.release()

    @callback
    def async_on_remove(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when entity is removed or not added."""
        if self._on_remove is None:
            self._on_remove = []
        self._on_remove.append(func)

    async def async_removed_from_registry(self) -> None:
        """Run when entity has been removed from entity registry.

        To be extended by integrations.
        """

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        if self._platform_state == EntityPlatformState.ADDED:
            raise HomeAssistantError(
                f"Entity {self.entity_id} cannot be added a second time to an entity"
                " platform"
            )

        self.hass = hass
        self.platform = platform
        self.parallel_updates = parallel_updates
        self._platform_state = EntityPlatformState.ADDED

    def _call_on_remove_callbacks(self) -> None:
        """Call callbacks registered by async_on_remove."""
        if self._on_remove is None:
            return
        while self._on_remove:
            self._on_remove.pop()()

    @callback
    def add_to_platform_abort(self) -> None:
        """Abort adding an entity to a platform."""

        self._platform_state = EntityPlatformState.NOT_ADDED
        self._call_on_remove_callbacks()

        self.hass = None  # type: ignore[assignment]
        self.platform = None  # type: ignore[assignment]
        self.parallel_updates = None

    async def add_to_platform_finish(self) -> None:
        """Finish adding an entity to a platform."""
        await self.async_internal_added_to_hass()
        await self.async_added_to_hass()
        self.async_write_ha_state()

    async def async_remove(self, *, force_remove: bool = False) -> None:
        """Remove entity from Home Assistant.

        If the entity has a non disabled entry in the entity registry,
        the entity's state will be set to unavailable, in the same way
        as when the entity registry is loaded.

        If the entity doesn't have a non disabled entry in the entity registry,
        or if force_remove=True, its state will be removed.
        """
        # The check for self.platform guards against integrations not using an
        # EntityComponent and can be removed in HA Core 2024.1
        if self.platform and self._platform_state != EntityPlatformState.ADDED:
            raise HomeAssistantError(
                f"Entity {self.entity_id} async_remove called twice"
            )

        self._platform_state = EntityPlatformState.REMOVED

        self._call_on_remove_callbacks()

        await self.async_internal_will_remove_from_hass()
        await self.async_will_remove_from_hass()

        # Check if entry still exists in entity registry (e.g. unloading config entry)
        if (
            not force_remove
            and self.registry_entry
            and not self.registry_entry.disabled
        ):
            # Set the entity's state will to unavailable + ATTR_RESTORED: True
            self.registry_entry.write_unavailable_state(self.hass)
        else:
            self.hass.states.async_remove(self.entity_id, context=self._context)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        To be extended by integrations.
        """

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        To be extended by integrations.
        """

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated.

        To be extended by integrations.
        """

    async def async_internal_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        Not to be extended by integrations.
        """
        info = {
            "domain": self.platform.platform_name,
            "custom_component": "custom_components" in type(self).__module__,
        }

        if self.platform.config_entry:
            info["source"] = SOURCE_CONFIG_ENTRY
            info["config_entry"] = self.platform.config_entry.entry_id
        else:
            info["source"] = SOURCE_PLATFORM_CONFIG

        self.hass.data[DATA_ENTITY_SOURCE][self.entity_id] = info

        if self.registry_entry is not None:
            # This is an assert as it should never happen, but helps in tests
            assert (
                not self.registry_entry.disabled_by
            ), f"Entity {self.entity_id} is being added while it's disabled"

            self.async_on_remove(
                async_track_entity_registry_updated_event(
                    self.hass, self.entity_id, self._async_registry_updated
                )
            )
            self._async_subscribe_device_updates()

    async def async_internal_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        Not to be extended by integrations.
        """
        # The check for self.platform guards against integrations not using an
        # EntityComponent and can be removed in HA Core 2024.1
        if self.platform:
            self.hass.data[DATA_ENTITY_SOURCE].pop(self.entity_id)

    async def _async_registry_updated(
        self, event: EventType[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Handle entity registry update."""
        data = event.data
        if data["action"] == "remove":
            await self.async_removed_from_registry()
            self.registry_entry = None
            await self.async_remove()

        if data["action"] != "update":
            return

        if "device_id" in data["changes"]:
            self._async_subscribe_device_updates()

        ent_reg = er.async_get(self.hass)
        old = self.registry_entry
        registry_entry = ent_reg.async_get(data["entity_id"])
        assert registry_entry is not None
        self.registry_entry = registry_entry

        if device_id := registry_entry.device_id:
            self.device_entry = dr.async_get(self.hass).async_get(device_id)

        if registry_entry.disabled:
            await self.async_remove()
            return

        assert old is not None
        if registry_entry.entity_id == old.entity_id:
            self.async_registry_entry_updated()
            self.async_write_ha_state()
            return

        await self.async_remove(force_remove=True)

        self.entity_id = registry_entry.entity_id
        await self.platform.async_add_entities([self])

    @callback
    def _async_unsubscribe_device_updates(self) -> None:
        """Unsubscribe from device registry updates."""
        if not self._unsub_device_updates:
            return
        self._unsub_device_updates()
        self._unsub_device_updates = None

    @callback
    def _async_device_registry_updated(
        self, event: EventType[EventDeviceRegistryUpdatedData]
    ) -> None:
        """Handle device registry update."""
        data = event.data

        if data["action"] != "update":
            return

        if "name" not in data["changes"] and "name_by_user" not in data["changes"]:
            return

        self.device_entry = dr.async_get(self.hass).async_get(data["device_id"])
        self.async_write_ha_state()

    @callback
    def _async_subscribe_device_updates(self) -> None:
        """Subscribe to device registry updates."""
        assert self.registry_entry

        self._async_unsubscribe_device_updates()

        if (device_id := self.registry_entry.device_id) is None:
            return

        if not self.has_entity_name:
            return

        self._unsub_device_updates = async_track_device_registry_updated_event(
            self.hass,
            device_id,
            self._async_device_registry_updated,
        )
        if (
            not self._on_remove
            or self._async_unsubscribe_device_updates not in self._on_remove
        ):
            self.async_on_remove(self._async_unsubscribe_device_updates)

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<entity {self.entity_id}={self._stringify_state(self.available)}>"

    async def async_request_call(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Process request batched."""
        if self.parallel_updates:
            await self.parallel_updates.acquire()

        try:
            return await coro
        finally:
            if self.parallel_updates:
                self.parallel_updates.release()

    def _suggest_report_issue(self) -> str:
        """Suggest to report an issue."""
        report_issue = ""
        if "custom_components" in type(self).__module__:
            report_issue = "report it to the custom integration author."
        else:
            report_issue = (
                "create a bug report at "
                "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
            )
            # The check for self.platform guards against integrations not using an
            # EntityComponent and can be removed in HA Core 2024.1
            if self.platform:
                report_issue += (
                    f"+label%3A%22integration%3A+{self.platform.platform_name}%22"
                )

        return report_issue


@dataclass(slots=True)
class ToggleEntityDescription(EntityDescription):
    """A class that describes toggle entities."""


class ToggleEntity(Entity):
    """An abstract class for entities that can be turned on and off."""

    entity_description: ToggleEntityDescription
    _attr_is_on: bool | None = None
    _attr_state: None = None

    @property
    @final
    def state(self) -> Literal["on", "off"] | None:
        """Return the state."""
        if (is_on := self.is_on) is None:
            return None
        return STATE_ON if is_on else STATE_OFF

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._attr_is_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        raise NotImplementedError()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.hass.async_add_executor_job(ft.partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        raise NotImplementedError()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.hass.async_add_executor_job(ft.partial(self.turn_off, **kwargs))

    @final
    def toggle(self, **kwargs: Any) -> None:
        """Toggle the entity.

        This method will never be called by Home Assistant and should not be implemented
        by integrations.
        """

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the entity.

        This method should typically not be implemented by integrations, it's enough to
        implement async_turn_on + async_turn_off or turn_on + turn_off.
        """
        if self.is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)
