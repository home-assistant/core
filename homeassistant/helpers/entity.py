"""An abstract class for entities."""

from __future__ import annotations

from abc import ABCMeta
import asyncio
from collections import deque
from collections.abc import Callable, Coroutine, Iterable, Mapping
import dataclasses
from enum import Enum, auto
import functools as ft
import logging
import math
from operator import attrgetter
import sys
import threading
import time
from types import FunctionType
from typing import TYPE_CHECKING, Any, Final, Literal, NotRequired, TypedDict, final

from propcache import cached_property
import voluptuous as vol

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
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    HassJobType,
    HomeAssistant,
    ReleaseChannel,
    callback,
    get_hassjob_callable_job_type,
    get_release_channel,
)
from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.exceptions import (
    HomeAssistantError,
    InvalidStateError,
    NoEntitySpecifiedError,
)
from homeassistant.loader import async_suggest_report_issue, bind_hass
from homeassistant.util import ensure_unique_string, slugify
from homeassistant.util.frozen_dataclass_compat import FrozenOrThawed

from . import device_registry as dr, entity_registry as er, singleton
from .device_registry import DeviceInfo, EventDeviceRegistryUpdatedData
from .event import (
    async_track_device_registry_updated_event,
    async_track_entity_registry_updated_event,
)
from .frame import ReportBehavior, report_non_thread_safe_operation, report_usage
from .typing import UNDEFINED, StateType, UndefinedType

timer = time.time

if TYPE_CHECKING:
    from .entity_platform import EntityPlatform

_LOGGER = logging.getLogger(__name__)
SLOW_UPDATE_WARNING = 10
DATA_ENTITY_SOURCE = "entity_info"

# Used when converting float states to string: limit precision according to machine
# epsilon to make the string representation readable
FLOAT_PRECISION = abs(int(math.floor(math.log10(abs(sys.float_info.epsilon))))) - 1

# How many times per hour we allow capabilities to be updated before logging a warning
CAPABILITIES_UPDATE_LIMIT = 100

CONTEXT_RECENT_TIME_SECONDS = 5  # Time that a context is considered recent


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up entity sources."""
    entity_sources(hass)


@callback
@bind_hass
@singleton.singleton(DATA_ENTITY_SOURCE)
def entity_sources(hass: HomeAssistant) -> dict[str, EntityInfo]:
    """Get the entity sources."""
    return {}


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
        return state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)  # type: ignore[no-any-return]

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


class EntityInfo(TypedDict):
    """Entity info."""

    domain: str
    custom_component: bool
    config_entry: NotRequired[str]


class StateInfo(TypedDict):
    """State info."""

    unrecorded_attributes: frozenset[str]


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


_SENTINEL = object()


class EntityDescription(metaclass=FrozenOrThawed, frozen_or_thawed=True):
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
    translation_placeholders: Mapping[str, str] | None = None
    unit_of_measurement: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class CalculatedState:
    """Container with state and attributes.

    Returned by Entity._async_calculate_state.
    """

    state: str
    # The union of all attributes, after overriding with entity registry settings
    attributes: dict[str, Any]
    # Capability attributes returned by the capability_attributes property
    capability_attributes: Mapping[str, Any] | None


class CachedProperties(type):
    """Metaclass which invalidates cached entity properties on write to _attr_.

    A class which has CachedProperties can optionally have a list of cached
    properties, passed as cached_properties, which must be a set of strings.
    - Each item in the cached_property set must be the name of a method decorated
      with @cached_property
    - For each item in the cached_property set, a property function with the
      same name, prefixed with _attr_, will be created
    - The property _attr_-property functions allow setting, getting and deleting
      data, which will be stored in an attribute prefixed with __attr_
    - The _attr_-property setter will invalidate the @cached_property by calling
      delattr on it
    """

    def __new__(
        mcs,  # noqa: N804  ruff bug, ruff does not understand this is a metaclass
        name: str,
        bases: tuple[type, ...],
        namespace: dict[Any, Any],
        cached_properties: set[str] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Start creating a new CachedProperties.

        Pop cached_properties and store it in the namespace.
        """
        namespace["_CachedProperties__cached_properties"] = cached_properties or set()
        return super().__new__(mcs, name, bases, namespace, **kwargs)

    def __init__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[Any, Any],
        **kwargs: Any,
    ) -> None:
        """Finish creating a new CachedProperties.

        Wrap _attr_ for cached properties in property objects.
        """

        def deleter(name: str) -> Callable[[Any], None]:
            """Create a deleter for an _attr_ property."""
            private_attr_name = f"__attr_{name}"

            def _deleter(o: Any) -> None:
                """Delete an _attr_ property.

                Does two things:
                - Delete the __attr_ attribute
                - Invalidate the cache of the cached property

                Raises AttributeError if the __attr_ attribute does not exist
                """
                # Invalidate the cache of the cached property
                o.__dict__.pop(name, None)
                # Delete the __attr_ attribute
                delattr(o, private_attr_name)

            return _deleter

        def setter(name: str) -> Callable[[Any, Any], None]:
            """Create a setter for an _attr_ property."""
            private_attr_name = f"__attr_{name}"

            def _setter(o: Any, val: Any) -> None:
                """Set an _attr_ property to the backing __attr attribute.

                Also invalidates the corresponding cached_property by calling
                delattr on it.
                """
                if (
                    old_val := getattr(o, private_attr_name, _SENTINEL)
                ) == val and type(old_val) is type(val):
                    return
                setattr(o, private_attr_name, val)
                # Invalidate the cache of the cached property
                o.__dict__.pop(name, None)

            return _setter

        def make_property(name: str) -> property:
            """Help create a property object."""
            return property(
                fget=attrgetter(f"__attr_{name}"), fset=setter(name), fdel=deleter(name)
            )

        def wrap_attr(cls: CachedProperties, property_name: str) -> None:
            """Wrap a cached property's corresponding _attr in a property.

            If the class being created has an _attr class attribute, move it, and its
            annotations, to the __attr attribute.
            """
            attr_name = f"_attr_{property_name}"
            private_attr_name = f"__attr_{property_name}"
            # Check if an _attr_ class attribute exits and move it to __attr_. We check
            # __dict__ here because we don't care about _attr_ class attributes in parents.
            if attr_name in cls.__dict__:
                attr = getattr(cls, attr_name)
                if isinstance(attr, (FunctionType, property)):
                    raise TypeError(f"Can't override {attr_name} in subclass")
                setattr(cls, private_attr_name, attr)
                annotations = cls.__annotations__
                if attr_name in annotations:
                    annotations[private_attr_name] = annotations.pop(attr_name)
            # Create the _attr_ property
            setattr(cls, attr_name, make_property(property_name))

        cached_properties: set[str] = namespace["_CachedProperties__cached_properties"]
        seen_props: set[str] = set()  # Keep track of properties which have been handled
        for property_name in cached_properties:
            wrap_attr(cls, property_name)
            seen_props.add(property_name)

        # Look for cached properties of parent classes where this class has
        # corresponding _attr_ class attributes and re-wrap them.
        for parent in cls.__mro__[:0:-1]:
            if "_CachedProperties__cached_properties" not in parent.__dict__:
                continue
            cached_properties = getattr(parent, "_CachedProperties__cached_properties")
            for property_name in cached_properties:
                if property_name in seen_props:
                    continue
                attr_name = f"_attr_{property_name}"
                # Check if an _attr_ class attribute exits. We check __dict__ here because
                # we don't care about _attr_ class attributes in parents.
                if (attr_name) not in cls.__dict__:
                    continue
                wrap_attr(cls, property_name)
                seen_props.add(property_name)


class ABCCachedProperties(CachedProperties, ABCMeta):
    """Add ABCMeta to CachedProperties."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "assumed_state",
    "attribution",
    "available",
    "capability_attributes",
    "device_class",
    "device_info",
    "entity_category",
    "has_entity_name",
    "entity_picture",
    "entity_registry_enabled_default",
    "entity_registry_visible_default",
    "extra_state_attributes",
    "force_update",
    "icon",
    "name",
    "should_poll",
    "state",
    "supported_features",
    "translation_key",
    "translation_placeholders",
    "unique_id",
    "unit_of_measurement",
}


class Entity(
    metaclass=ABCCachedProperties, cached_properties=CACHED_PROPERTIES_WITH_ATTR_
):
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

    # If we reported deprecated supported features constants
    _deprecated_supported_features_reported = False

    # If we reported this entity is updated while disabled
    _disabled_reported = False

    # If we reported this entity is using async_update_ha_state, while
    # it should be using async_write_ha_state.
    _async_update_ha_state_reported = False

    # If we reported the name translation placeholders do not match the name
    _name_translation_placeholders_reported = False

    # Protect for multiple updates
    _update_staged = False

    # _verified_state_writable is set to True if the entity has been verified
    # to be writable. This is used to avoid repeated checks.
    _verified_state_writable = False

    # Process updates in parallel
    parallel_updates: asyncio.Semaphore | None = None

    # Entry in the entity registry
    registry_entry: er.RegistryEntry | None = None

    # If the entity is removed from the entity registry
    _removed_from_registry: bool = False

    # The device entry for this entity
    device_entry: dr.DeviceEntry | None = None

    # Hold list for functions to call on remove.
    _on_remove: list[CALLBACK_TYPE] | None = None

    _unsub_device_updates: CALLBACK_TYPE | None = None

    # Context
    _context: Context | None = None
    _context_set: float | None = None

    # If entity is added to an entity platform
    _platform_state = EntityPlatformState.NOT_ADDED

    # Attributes to exclude from recording, only set by base components, e.g. light
    _entity_component_unrecorded_attributes: frozenset[str] = frozenset()
    # Additional integration specific attributes to exclude from recording, set by
    # platforms, e.g. a derived class in hue.light
    _unrecorded_attributes: frozenset[str] = frozenset()
    # Union of _entity_component_unrecorded_attributes and _unrecorded_attributes,
    # set automatically by __init_subclass__
    __combined_unrecorded_attributes: frozenset[str] = (
        _entity_component_unrecorded_attributes | _unrecorded_attributes
    )
    # Job type cache
    _job_types: dict[str, HassJobType] | None = None

    # StateInfo. Set by EntityPlatform by calling async_internal_added_to_hass
    # While not purely typed, it makes typehinting more useful for us
    # and removes the need for constant None checks or asserts.
    _state_info: StateInfo = None  # type: ignore[assignment]

    __capabilities_updated_at: deque[float]
    __capabilities_updated_at_reported: bool = False
    __remove_future: asyncio.Future[None] | None = None

    # Entity Properties
    _attr_assumed_state: bool = False
    _attr_attribution: str | None = None
    _attr_available: bool = True
    _attr_capability_attributes: dict[str, Any] | None = None
    _attr_device_class: str | None
    _attr_device_info: DeviceInfo | None = None
    _attr_entity_category: EntityCategory | None
    _attr_has_entity_name: bool
    _attr_entity_picture: str | None = None
    _attr_entity_registry_enabled_default: bool
    _attr_entity_registry_visible_default: bool
    _attr_extra_state_attributes: dict[str, Any]
    _attr_force_update: bool
    _attr_icon: str | None
    _attr_name: str | None
    _attr_should_poll: bool = True
    _attr_state: StateType = STATE_UNKNOWN
    _attr_supported_features: int | None = None
    _attr_translation_key: str | None
    _attr_translation_placeholders: Mapping[str, str]
    _attr_unique_id: str | None = None
    _attr_unit_of_measurement: str | None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Initialize an Entity subclass."""
        super().__init_subclass__(**kwargs)
        cls.__combined_unrecorded_attributes = (
            cls._entity_component_unrecorded_attributes | cls._unrecorded_attributes
        )

    def get_hassjob_type(self, function_name: str) -> HassJobType:
        """Get the job type function for the given name.

        This is used for entity service calls to avoid
        figuring out the job type each time.
        """
        if not self._job_types:
            self._job_types = {}
        if function_name not in self._job_types:
            self._job_types[function_name] = get_hassjob_callable_job_type(
                getattr(self, function_name)
            )
        return self._job_types[function_name]

    @cached_property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return self._attr_should_poll

    @cached_property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._attr_unique_id

    @cached_property
    def use_device_name(self) -> bool:
        """Return if this entity does not have its own name.

        Should be True if the entity represents the single main feature of a device.
        """
        if hasattr(self, "_attr_name"):
            return not self._attr_name
        if (
            name_translation_key := self._name_translation_key
        ) and name_translation_key in self.platform.platform_translations:
            return False
        if hasattr(self, "entity_description"):
            return not self.entity_description.name
        return not self.name

    @cached_property
    def has_entity_name(self) -> bool:
        """Return if the name of the entity is describing only the entity itself."""
        if hasattr(self, "_attr_has_entity_name"):
            return self._attr_has_entity_name
        if hasattr(self, "entity_description"):
            return self.entity_description.has_entity_name
        return False

    def _device_class_name_helper(
        self,
        component_translations: dict[str, str],
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

    @cached_property
    def _unit_of_measurement_translation_key(self) -> str | None:
        """Return translation key for unit of measurement."""
        if self.translation_key is None:
            return None
        if self.platform is None:
            raise ValueError(
                f"Entity {type(self)} cannot have a translation key for "
                "unit of measurement before being added to the entity platform"
            )
        platform = self.platform
        return (
            f"component.{platform.platform_name}.entity.{platform.domain}"
            f".{self.translation_key}.unit_of_measurement"
        )

    def _substitute_name_placeholders(self, name: str) -> str:
        """Substitute placeholders in entity name."""
        try:
            return name.format(**self.translation_placeholders)
        except KeyError as err:
            if not self._name_translation_placeholders_reported:
                if get_release_channel() is not ReleaseChannel.STABLE:
                    raise HomeAssistantError(f"Missing placeholder {err}") from err
                report_issue = self._suggest_report_issue()
                _LOGGER.warning(
                    (
                        "Entity %s (%s) has translation placeholders '%s' which do not "
                        "match the name '%s', please %s"
                    ),
                    self.entity_id,
                    type(self),
                    self.translation_placeholders,
                    name,
                    report_issue,
                )
                self._name_translation_placeholders_reported = True
            return name

    def _name_internal(
        self,
        device_class_name: str | None,
        platform_translations: dict[str, str],
    ) -> str | UndefinedType | None:
        """Return the name of the entity."""
        if hasattr(self, "_attr_name"):
            return self._attr_name
        if (
            self.has_entity_name
            and (name_translation_key := self._name_translation_key)
            and (name := platform_translations.get(name_translation_key))
        ):
            return self._substitute_name_placeholders(name)
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
        if (
            # Check our class has overridden the name property from Entity
            # We need to use type.__getattribute__ to retrieve the underlying
            # property or cached_property object instead of the property's
            # value.
            type.__getattribute__(self.__class__, "name")
            is type.__getattribute__(Entity, "name")
        ):
            name = self._name_internal(
                self._object_id_device_class_name,
                self.platform.object_id_platform_translations,
            )
        else:
            name = self.name
        return None if name is UNDEFINED else name

    @cached_property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""
        return self._name_internal(
            self._device_class_name,
            self.platform.platform_translations,
        )

    @cached_property
    def state(self) -> StateType:
        """Return the state of the entity."""
        return self._attr_state

    @cached_property
    def capability_attributes(self) -> dict[str, Any] | None:
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

    @cached_property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes.

        Implemented by component base class, should not be extended by integrations.
        Convention for attribute names is lowercase snake_case.
        """
        return None

    @cached_property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        if hasattr(self, "_attr_extra_state_attributes"):
            return self._attr_extra_state_attributes
        return None

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return self._attr_device_info

    @cached_property
    def device_class(self) -> str | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @cached_property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity, if any."""
        if hasattr(self, "_attr_unit_of_measurement"):
            return self._attr_unit_of_measurement
        if hasattr(self, "entity_description"):
            return self.entity_description.unit_of_measurement
        return None

    @cached_property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if hasattr(self, "_attr_icon"):
            return self._attr_icon
        if hasattr(self, "entity_description"):
            return self.entity_description.icon
        return None

    @cached_property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        return self._attr_entity_picture

    @cached_property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available

    @cached_property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return self._attr_assumed_state

    @cached_property
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

    @cached_property
    def supported_features(self) -> int | None:
        """Flag supported features."""
        return self._attr_supported_features

    @cached_property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added.

        This only applies when fist added to the entity registry.
        """
        if hasattr(self, "_attr_entity_registry_enabled_default"):
            return self._attr_entity_registry_enabled_default
        if hasattr(self, "entity_description"):
            return self.entity_description.entity_registry_enabled_default
        return True

    @cached_property
    def entity_registry_visible_default(self) -> bool:
        """Return if the entity should be visible when first added.

        This only applies when fist added to the entity registry.
        """
        if hasattr(self, "_attr_entity_registry_visible_default"):
            return self._attr_entity_registry_visible_default
        if hasattr(self, "entity_description"):
            return self.entity_description.entity_registry_visible_default
        return True

    @cached_property
    def attribution(self) -> str | None:
        """Return the attribution."""
        return self._attr_attribution

    @cached_property
    def entity_category(self) -> EntityCategory | None:
        """Return the category of the entity, if any."""
        if hasattr(self, "_attr_entity_category"):
            return self._attr_entity_category
        if hasattr(self, "entity_description"):
            return self.entity_description.entity_category
        return None

    @cached_property
    def translation_key(self) -> str | None:
        """Return the translation key to translate the entity's states."""
        if hasattr(self, "_attr_translation_key"):
            return self._attr_translation_key
        if hasattr(self, "entity_description"):
            return self.entity_description.translation_key
        return None

    @final
    @cached_property
    def translation_placeholders(self) -> Mapping[str, str]:
        """Return the translation placeholders for translated entity's name."""
        if hasattr(self, "_attr_translation_placeholders"):
            return self._attr_translation_placeholders
        if hasattr(self, "entity_description"):
            return self.entity_description.translation_placeholders or {}
        return {}

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
        self._context_set = time.time()

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
            except Exception:
                _LOGGER.exception("Update for %s fails", self.entity_id)
                return
        elif not self._async_update_ha_state_reported:
            report_issue = self._suggest_report_issue()
            _LOGGER.warning(
                (
                    "Entity %s (%s) is using self.async_update_ha_state(), without"
                    " enabling force_refresh. Instead it should use"
                    " self.async_write_ha_state(), please %s"
                ),
                self.entity_id,
                type(self),
                report_issue,
            )
            self._async_update_ha_state_reported = True

        self._async_write_ha_state()

    @callback
    def _async_verify_state_writable(self) -> None:
        """Verify the entity is in a writable state."""
        if self.hass is None:
            raise RuntimeError(f"Attribute hass is None for {self}")

        # Break if entity is not loaded using EntityComponent
        # behavior changed from logging in in 2025.1
        if self.platform is None:
            report_usage(  # type: ignore[unreachable]
                f"Entity {self.entity_id} ({type(self)}) does not have a platform,"
                "this may be caused by adding it manually instead of with an EntityComponent helper",
                core_behavior=ReportBehavior.ERROR,
            )

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                f"No entity id specified for entity {self.name}"
            )

        self._verified_state_writable = True

    @callback
    def _async_write_ha_state_from_call_soon_threadsafe(self) -> None:
        """Write the state to the state machine from the event loop thread."""
        if not self.hass or not self._verified_state_writable:
            self._async_verify_state_writable()
        self._async_write_ha_state()

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        if not self.hass or not self._verified_state_writable:
            self._async_verify_state_writable()
        if self.hass.loop_thread_id != threading.get_ident():
            report_non_thread_safe_operation("async_write_ha_state")
        self._async_write_ha_state()

    def _stringify_state(self, available: bool) -> str:
        """Convert state to string."""
        if not available:
            return STATE_UNAVAILABLE
        if (state := self.state) is None:
            return STATE_UNKNOWN
        if type(state) is str:  # noqa: E721
            # fast path for strings
            return state
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
        if name is None and self.use_device_name:
            return device_name
        return f"{device_name} {name}" if device_name else name

    @callback
    def _async_calculate_state(self) -> CalculatedState:
        """Calculate state string and attribute mapping."""
        state, attr, capabilities, _, _ = self.__async_calculate_state()
        return CalculatedState(state, attr, capabilities)

    def __async_calculate_state(
        self,
    ) -> tuple[str, dict[str, Any], Mapping[str, Any] | None, str | None, int | None]:
        """Calculate state string and attribute mapping.

        Returns a tuple:
        state - the stringified state
        attr - the attribute dictionary
        capability_attr - a mapping with capability attributes
        original_device_class - the device class which may be overridden
        supported_features - the supported features

        This method is called when writing the state to avoid the overhead of creating
        a dataclass object.
        """
        entry = self.registry_entry

        capability_attr = self.capability_attributes
        attr = capability_attr.copy() if capability_attr else {}

        available = self.available  # only call self.available once per update cycle
        state = self._stringify_state(available)
        if available:
            if state_attributes := self.state_attributes:
                attr.update(state_attributes)
            if extra_state_attributes := self.extra_state_attributes:
                attr.update(extra_state_attributes)

        if (unit_of_measurement := self.unit_of_measurement) is not None:
            attr[ATTR_UNIT_OF_MEASUREMENT] = unit_of_measurement

        if assumed_state := self.assumed_state:
            attr[ATTR_ASSUMED_STATE] = assumed_state

        if (attribution := self.attribution) is not None:
            attr[ATTR_ATTRIBUTION] = attribution

        original_device_class = self.device_class
        if (
            device_class := (entry and entry.device_class) or original_device_class
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

        return (state, attr, capability_attr, original_device_class, supported_features)

    @callback
    def _async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        if self._platform_state is EntityPlatformState.REMOVED:
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

        state_calculate_start = timer()
        state, attr, capabilities, original_device_class, supported_features = (
            self.__async_calculate_state()
        )
        time_now = timer()

        if entry:
            # Make sure capabilities in the entity registry are up to date. Capabilities
            # include capability attributes, device class and supported features
            supported_features = supported_features or 0
            if (
                capabilities != entry.capabilities
                or original_device_class != entry.original_device_class
                or supported_features != entry.supported_features
            ):
                if not self.__capabilities_updated_at_reported:
                    # _Entity__capabilities_updated_at is because of name mangling
                    if not (
                        capabilities_updated_at := getattr(
                            self, "_Entity__capabilities_updated_at", None
                        )
                    ):
                        self.__capabilities_updated_at = deque(
                            maxlen=CAPABILITIES_UPDATE_LIMIT + 1
                        )
                        capabilities_updated_at = self.__capabilities_updated_at
                    capabilities_updated_at.append(time_now)
                    while time_now - capabilities_updated_at[0] > 3600:
                        capabilities_updated_at.popleft()
                    if len(capabilities_updated_at) > CAPABILITIES_UPDATE_LIMIT:
                        self.__capabilities_updated_at_reported = True
                        report_issue = self._suggest_report_issue()
                        _LOGGER.warning(
                            (
                                "Entity %s (%s) is updating its capabilities too often,"
                                " please %s"
                            ),
                            entity_id,
                            type(self),
                            report_issue,
                        )
                entity_registry = er.async_get(self.hass)
                self.registry_entry = entity_registry.async_update_entity(
                    self.entity_id,
                    capabilities=capabilities,
                    original_device_class=original_device_class,
                    supported_features=supported_features,
                )

        if time_now - state_calculate_start > 0.4 and not self._slow_reported:
            self._slow_reported = True
            report_issue = self._suggest_report_issue()
            _LOGGER.warning(
                "Updating state for %s (%s) took %.3f seconds. Please %s",
                entity_id,
                type(self),
                time_now - state_calculate_start,
                report_issue,
            )

        try:
            # Most of the time this will already be
            # set and since try is near zero cost
            # on py3.11+ its faster to assume it is
            # set and catch the exception if it is not.
            customize = hass.data[DATA_CUSTOMIZE]
        except KeyError:
            pass
        else:
            # Overwrite properties that have been set in the config file.
            if custom := customize.get(entity_id):
                attr.update(custom)

        if (
            self._context_set is not None
            and time_now - self._context_set > CONTEXT_RECENT_TIME_SECONDS
        ):
            self._context = None
            self._context_set = None

        try:
            hass.states.async_set_internal(
                entity_id,
                state,
                attr,
                self.force_update,
                self._context,
                self._state_info,
                time_now,
            )
        except InvalidStateError:
            _LOGGER.exception(
                "Failed to set state for %s, fall back to %s", entity_id, STATE_UNKNOWN
            )
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
            self.hass.loop.call_soon_threadsafe(
                self._async_write_ha_state_from_call_soon_threadsafe
            )

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
                eager_start=True,
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
        if self._platform_state is not EntityPlatformState.NOT_ADDED:
            raise HomeAssistantError(
                f"Entity '{self.entity_id}' cannot be added a second time to an entity"
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

        self._platform_state = EntityPlatformState.REMOVED
        self._call_on_remove_callbacks()

        self.hass = None  # type: ignore[assignment]
        self.platform = None  # type: ignore[assignment]
        self.parallel_updates = None

    async def add_to_platform_finish(self) -> None:
        """Finish adding an entity to a platform."""
        await self.async_internal_added_to_hass()
        await self.async_added_to_hass()
        self.async_write_ha_state()

    @final
    async def async_remove(self, *, force_remove: bool = False) -> None:
        """Remove entity from Home Assistant.

        If the entity has a non disabled entry in the entity registry,
        the entity's state will be set to unavailable, in the same way
        as when the entity registry is loaded.

        If the entity doesn't have a non disabled entry in the entity registry,
        or if force_remove=True, its state will be removed.
        """
        if self.__remove_future is not None:
            await self.__remove_future
            return

        self.__remove_future = self.hass.loop.create_future()
        try:
            await self.__async_remove_impl(force_remove)
        except BaseException as ex:
            self.__remove_future.set_exception(ex)
            raise
        finally:
            self.__remove_future.set_result(None)

    @final
    async def __async_remove_impl(self, force_remove: bool) -> None:
        """Remove entity from Home Assistant."""

        self._platform_state = EntityPlatformState.REMOVED

        self._call_on_remove_callbacks()

        await self.async_internal_will_remove_from_hass()
        await self.async_will_remove_from_hass()

        # Check if entry still exists in entity registry (e.g. unloading config entry)
        if (
            not force_remove
            and self.registry_entry
            and not self.registry_entry.disabled
            # Check if entity is still in the entity registry
            # by checking self._removed_from_registry
            #
            # Because self.registry_entry is unset in a task,
            # its possible that the entity has been removed but
            # the task has not yet been executed.
            #
            # self._removed_from_registry is set to True in a
            # callback which does not have the same issue.
            #
            and not self._removed_from_registry
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
        is_custom_component = "custom_components" in type(self).__module__
        entity_info: EntityInfo = {
            "domain": self.platform.platform_name,
            "custom_component": is_custom_component,
        }
        if self.platform.config_entry:
            entity_info["config_entry"] = self.platform.config_entry.entry_id

        entity_sources(self.hass)[self.entity_id] = entity_info

        self._state_info = {
            "unrecorded_attributes": self.__combined_unrecorded_attributes
        }

        if self.registry_entry is not None:
            # This is an assert as it should never happen, but helps in tests
            assert (
                not self.registry_entry.disabled_by
            ), f"Entity '{self.entity_id}' is being added while it's disabled"

            self.async_on_remove(
                async_track_entity_registry_updated_event(
                    self.hass,
                    self.entity_id,
                    self._async_registry_updated,
                    job_type=HassJobType.Callback,
                )
            )
            self._async_subscribe_device_updates()

    async def async_internal_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        Not to be extended by integrations.
        """
        del entity_sources(self.hass)[self.entity_id]

    @callback
    def _async_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Handle entity registry update."""
        action = event.data["action"]
        is_remove = action == "remove"
        self._removed_from_registry = is_remove
        if action == "update" or is_remove:
            self.hass.async_create_task_internal(
                self._async_process_registry_update_or_remove(event), eager_start=True
            )

    async def _async_process_registry_update_or_remove(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Handle entity registry update or remove."""
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

        # Clear the remove future to handle entity added again after entity id change
        self.__remove_future = None
        self._platform_state = EntityPlatformState.NOT_ADDED
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
        self, event: Event[EventDeviceRegistryUpdatedData]
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
            job_type=HassJobType.Callback,
        )
        if (
            not self._on_remove
            or self._async_unsubscribe_device_updates not in self._on_remove
        ):
            self.async_on_remove(self._async_unsubscribe_device_updates)

    def __repr__(self) -> str:
        """Return the representation.

        If the entity is not added to a platform it's not safe to call _stringify_state.
        """
        if self._platform_state is not EntityPlatformState.ADDED:
            return f"<entity unknown.unknown={STATE_UNKNOWN}>"
        return f"<entity {self.entity_id}={self._stringify_state(self.available)}>"

    async def async_request_call[_T](self, coro: Coroutine[Any, Any, _T]) -> _T:
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
        platform_name = self.platform.platform_name
        return async_suggest_report_issue(
            self.hass, integration_domain=platform_name, module=type(self).__module__
        )


class ToggleEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes toggle entities."""


TOGGLE_ENTITY_CACHED_PROPERTIES_WITH_ATTR_ = {"is_on"}


class ToggleEntity(
    Entity, cached_properties=TOGGLE_ENTITY_CACHED_PROPERTIES_WITH_ATTR_
):
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

    @cached_property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._attr_is_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        raise NotImplementedError

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.hass.async_add_executor_job(ft.partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        raise NotImplementedError

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
