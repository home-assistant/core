"""Device types: what a device is, and the roles its entities play on it."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
import logging
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, overload, override

from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey

from . import device_registry as dr, entity_registry as er

if TYPE_CHECKING:
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    from homeassistant.components.button import ButtonDeviceClass
    from homeassistant.components.cover import CoverDeviceClass
    from homeassistant.components.event import EventDeviceClass
    from homeassistant.components.humidifier import HumidifierDeviceClass
    from homeassistant.components.image_processing import ImageProcessingDeviceClass
    from homeassistant.components.media_player import MediaPlayerDeviceClass
    from homeassistant.components.number import NumberDeviceClass
    from homeassistant.components.sensor import SensorDeviceClass
    from homeassistant.components.switch import SwitchDeviceClass
    from homeassistant.components.update import UpdateDeviceClass
    from homeassistant.components.valve import ValveDeviceClass

_LOGGER = logging.getLogger(__name__)

GENERIC_TYPE_ID = "generic"

DATA_DEVICE_TYPES: HassKey[_DeviceTypesData] = HassKey("device_types")

# Entity registry changes that can make a unique id resolve to another entity, or
# change whether the entity fits its slot
_ENTITY_RESOLUTION_CHANGES = frozenset(
    {"device_class", "entity_id", "original_device_class", "platform", "unique_id"}
)

type DeviceClass = (
    BinarySensorDeviceClass
    | ButtonDeviceClass
    | CoverDeviceClass
    | EventDeviceClass
    | HumidifierDeviceClass
    | ImageProcessingDeviceClass
    | MediaPlayerDeviceClass
    | NumberDeviceClass
    | SensorDeviceClass
    | SwitchDeviceClass
    | UpdateDeviceClass
    | ValveDeviceClass
)
type Accepts = Platform | DeviceClass

_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_TYPE_ID = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
_COMPONENT_MODULE = re.compile(r"homeassistant\.components\.(\w+)(?:\.|$)")

_VOCABULARY: dict[str, type[DeviceType]] = {}


def _snake_case(name: str) -> str:
    return _WORD_BOUNDARY.sub("_", name).lower()


def _device_class_domain(device_class: DeviceClass) -> str:
    """Return the entity domain a device class enum member belongs to.

    Device class enums live in their entity platform's package, which this helper
    only imports for type checking, so the domain comes from the enum's module path.
    """
    if not isinstance(device_class, StrEnum):
        raise TypeError(
            f"A slot accepts platforms and device classes, not {device_class!r}"
        )
    module = type(device_class).__module__
    if (
        not type(device_class).__name__.endswith("DeviceClass")
        or (match := _COMPONENT_MODULE.match(module)) is None
        or match[1] not in {platform.value for platform in Platform}
    ):
        raise TypeError(
            f"{device_class!r} is not a device class of an entity platform"
            f" (defined in {module})"
        )
    return match[1]


class DeviceSlot:
    """A named role an entity plays on a device type, declared in the class body."""

    slot_id: str
    defined_by: type

    def __init__(self, *accepts: Accepts, required: bool = False) -> None:
        """Initialize the slot with what it accepts."""
        if not accepts:
            raise TypeError("A slot must accept at least one platform or device class")
        matches: dict[tuple[str, str | None], None] = {}
        for accepted in accepts:
            if isinstance(accepted, Platform):
                matches[accepted.value, None] = None
            else:
                matches[_device_class_domain(accepted), accepted.value] = None
        self.accepts: tuple[Accepts, ...] = accepts
        self.required = required
        self._matches = frozenset(matches)
        self._entity_domains = tuple(dict.fromkeys(domain for domain, _ in matches))

    @overload
    def __get__(
        self, instance: DeviceType, owner: type[DeviceType]
    ) -> tuple[EntityReference, ...]: ...

    @overload
    def __get__(self, instance: None, owner: type[DeviceType]) -> DeviceSlot: ...

    def __get__(
        self, instance: DeviceType | None, owner: type[DeviceType]
    ) -> DeviceSlot | tuple[EntityReference, ...]:
        """Return the references on a device type instance, else the declaration."""
        if instance is None:
            return self
        return instance.references.get(self.slot_id, ())

    @override
    def __repr__(self) -> str:
        """Return the representation."""
        name = getattr(self, "slot_id", "<unbound>")
        return f"<DeviceSlot {name} accepts={self.accepts!r} required={self.required}>"

    @property
    def entity_domains(self) -> tuple[str, ...]:
        """Return the entity domains the slot accepts entities of."""
        return self._entity_domains

    def accepts_same_as(self, other: DeviceSlot) -> bool:
        """Return if both slots accept the same entities.

        Members of different enums with the same value are equal, so the enum
        members themselves cannot be compared.
        """
        return self._matches == other._matches

    def accepts_entity(self, domain: str, device_class: str | None) -> bool:
        """Return if an entity with this domain and device class fits the slot."""
        return (domain, None) in self._matches or (
            device_class is not None and (domain, device_class) in self._matches
        )


@dataclass(frozen=True, slots=True)
class EntityReference:
    """An entity, referenced the way its integration registers it."""

    platform: Platform
    integration_domain: str
    unique_id: str

    def __post_init__(self) -> None:
        """Check the reference, as the device registry stores it."""
        if (
            not isinstance(self.platform, Platform)
            or not isinstance(self.integration_domain, str)
            or not isinstance(self.unique_id, str)
        ):
            raise TypeError(
                "An entity reference takes a platform, the domain of the integration"
                f" and a unique id, not {self!r}"
            )


def _slot_references(slot: DeviceSlot, value: object) -> tuple[EntityReference, ...]:
    """Return the entities a slot is filled with as references without duplicates."""
    references: tuple[Any, ...]
    if isinstance(value, Iterable) and not isinstance(value, str):
        references = tuple(value)
    else:
        references = (value,)
    for reference in references:
        if not isinstance(reference, EntityReference):
            raise TypeError(
                f"Slot {slot.slot_id} takes an entity reference or several of them,"
                f" not {value!r}"
            )
        if reference.platform not in slot.entity_domains:
            raise TypeError(
                f"Slot {slot.slot_id} takes entities of"
                f" {', '.join(slot.entity_domains)}, not {reference.platform}"
            )
    return tuple(dict.fromkeys(references))


class DeviceType:
    """What a device is. The base class is the generic type of every device.

    An instance is the type of one device: it holds references to the entities
    filling its slots.
    """

    type_id: ClassVar[str] = GENERIC_TYPE_ID
    declared_slots: ClassVar[Mapping[str, DeviceSlot]] = MappingProxyType({})

    @override
    def __init_subclass__(cls, *, type_id: str | None = None, **kwargs: Any) -> None:
        """Name and collect the slots, check the declaration and register the type."""
        super().__init_subclass__(**kwargs)
        if type_id is None:
            type_id = _snake_case(cls.__name__)
        if not _TYPE_ID.fullmatch(type_id):
            raise ValueError(f"Invalid device type id {type_id!r} for {cls.__name__}")
        if (existing := _VOCABULARY.get(type_id)) is not None:
            raise TypeError(
                f"Device type id {type_id!r} of {cls.__qualname__} is already used"
                f" by {existing.__module__}.{existing.__qualname__}"
            )

        slots: dict[str, DeviceSlot] = {}
        for klass in reversed(cls.__mro__):
            for name, value in vars(klass).items():
                if not isinstance(value, DeviceSlot):
                    continue
                if name in _RESERVED_NAMES:
                    raise TypeError(
                        f"DeviceSlot {klass.__name__}.{name} uses a name reserved by"
                        " DeviceType"
                    )
                if not hasattr(value, "slot_id"):
                    value.slot_id = name
                    value.defined_by = klass
                elif value.slot_id != name or value.defined_by is not klass:
                    raise TypeError(
                        f"DeviceSlot {value.defined_by.__name__}.{value.slot_id}"
                        f" cannot also be {klass.__name__}.{name}"
                    )
                if (inherited := slots.get(name)) is not None:
                    _check_redeclaration(inherited, value)
                slots[name] = value
        for name, slot in slots.items():
            if getattr(cls, name) is not slot:
                raise TypeError(
                    f"{cls.__name__}.{name} overrides slot {name} of"
                    f" {slot.defined_by.__name__} with something else"
                )

        cls.type_id = type_id
        cls.declared_slots = MappingProxyType(slots)
        _VOCABULARY[type_id] = cls

    def __init__(
        self, /, **references: EntityReference | Iterable[EntityReference]
    ) -> None:
        """Fill the slots with references to the entities playing their role."""
        if unknown := references.keys() - self.declared_slots.keys():
            raise TypeError(
                f"{type(self).__name__} has no slot {', '.join(sorted(unknown))}"
            )
        filled = {
            slot_id: _slot_references(self.declared_slots[slot_id], value)
            for slot_id, value in references.items()
        }
        self.references: Mapping[str, tuple[EntityReference, ...]] = MappingProxyType(
            {slot_id: slot for slot_id, slot in filled.items() if slot}
        )

    @override
    def __setattr__(self, name: str, value: Any) -> None:
        """Refuse to shadow a slot on an instance."""
        if name in self.declared_slots:
            raise AttributeError(f"{name} is a slot and cannot be set")
        super().__setattr__(name, value)

    @override
    def __eq__(self, other: object) -> bool:
        """Return if this is the same type with the same entities in its slots."""
        return type(other) is type(self) and other.references == self.references

    @override
    def __hash__(self) -> int:
        """Return the hash."""
        return hash((type(self), frozenset(self.references.items())))

    @override
    def __repr__(self) -> str:
        """Return the representation."""
        slots = ", ".join(
            f"{slot_id}={slot!r}" for slot_id, slot in self.references.items()
        )
        return f"{type(self).__name__}({slots})"


def _check_redeclaration(inherited: DeviceSlot, slot: DeviceSlot) -> None:
    """Check a redeclared slot only makes its inherited slot required."""
    if not slot.accepts_same_as(inherited):
        raise TypeError(
            f"{slot.defined_by.__name__}.{slot.slot_id} cannot change what slot"
            f" {inherited.defined_by.__name__}.{inherited.slot_id} accepts"
        )
    if inherited.required and not slot.required:
        raise TypeError(
            f"{slot.defined_by.__name__}.{slot.slot_id} cannot make required slot"
            f" {inherited.defined_by.__name__}.{inherited.slot_id} optional"
        )


_RESERVED_NAMES = frozenset(
    {"references"} | {name for name in vars(DeviceType) if not name.startswith("_")}
)
_VOCABULARY[GENERIC_TYPE_ID] = DeviceType


def get_device_type_class(type_id: str) -> type[DeviceType] | None:
    """Return the device type class with this id."""
    return _VOCABULARY.get(type_id)


def get_device_type_classes() -> Mapping[str, type[DeviceType]]:
    """Return all registered device type classes by id."""
    return MappingProxyType(_VOCABULARY)


@dataclass(frozen=True, slots=True)
class BoundDeviceType:
    """The type of a device in the registry and the entities filling its slots."""

    device: dr.AnyDeviceEntry
    device_type: DeviceType
    entity_ids: Mapping[str, tuple[str, ...]]

    @property
    def missing_required(self) -> frozenset[str]:
        """Return the ids of the required slots without an entity."""
        return frozenset(
            slot_id
            for slot_id, slot in self.device_type.declared_slots.items()
            if slot.required and not self.entity_ids[slot_id]
        )


@dataclass(slots=True)
class _DeviceTypesData:
    """The cached bound device types and the slot fits already warned about."""

    bound: dict[str, BoundDeviceType]
    warned: set[tuple[str, str, EntityReference]]


@callback
def async_get_bound_device_type(
    hass: HomeAssistant, device_id: str
) -> BoundDeviceType | None:
    """Return the type of a device bound to its entities, None without the device.

    Disabled entities fill slots too, as slots describe the structure of the device.
    """
    if (data := hass.data.get(DATA_DEVICE_TYPES)) is None:
        data = hass.data[DATA_DEVICE_TYPES] = _DeviceTypesData({}, set())
        _async_setup_invalidation(hass, data.bound)
    if (bound := data.bound.get(device_id)) is not None:
        return bound
    if (
        device := dr.async_get(hass).async_get(
            device_id, include_composite_devices=False
        )
    ) is None:
        return None
    if (
        not isinstance(device, dr.DeviceEntry)
        or device.original_device_type is None
        or (type_class := get_device_type_class(device.original_device_type)) is None
    ):
        bound = data.bound[device_id] = BoundDeviceType(device, DeviceType(), {})
        return bound
    device_type = type_class(
        **{
            slot_id: [
                EntityReference(Platform(domain), integration_domain, unique_id)
                for domain, integration_domain, unique_id in references
                if domain in slot.entity_domains
            ]
            for slot_id, references in device.original_device_slots.items()
            if (slot := type_class.declared_slots.get(slot_id)) is not None
        }
    )
    bound = data.bound[device_id] = BoundDeviceType(
        device,
        device_type,
        {
            slot_id: _async_resolve_slot(
                hass,
                data.warned,
                device,
                slot,
                device_type.references.get(slot_id, ()),
            )
            for slot_id, slot in type_class.declared_slots.items()
        },
    )
    return bound


@callback
def _async_resolve_slot(
    hass: HomeAssistant,
    warned: set[tuple[str, str, EntityReference]],
    device: dr.DeviceEntry,
    slot: DeviceSlot,
    references: tuple[EntityReference, ...],
) -> tuple[str, ...]:
    """Return the ids of the referenced entities that fit the slot."""
    entity_registry = er.async_get(hass)
    entity_ids: dict[str, None] = {}
    for reference in references:
        if (
            entity_id := entity_registry.async_get_entity_id(
                reference.platform, reference.integration_domain, reference.unique_id
            )
        ) is None:
            continue
        entry = entity_registry.entities[entity_id]
        if slot.accepts_entity(
            reference.platform, entry.device_class or entry.original_device_class
        ):
            entity_ids[entity_id] = None
            continue
        if (key := (device.id, slot.slot_id, reference)) in warned:
            continue
        warned.add(key)
        _LOGGER.warning(
            "Entity %s with unique ID %s does not fit slot %s of device type %s"
            " of device %s, which accepts %s",
            entity_id,
            reference.unique_id,
            slot.slot_id,
            device.original_device_type,
            device.id,
            ", ".join(str(accepted) for accepted in slot.accepts),
        )
    return tuple(entity_ids)


@callback
def _async_setup_invalidation(
    hass: HomeAssistant, cache: dict[str, BoundDeviceType]
) -> None:
    """Drop cached bound device types when a registry change can affect them."""

    @callback
    def _async_device_updated(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        cache.pop(event.data["device_id"], None)

    @callback
    def _async_entity_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        # A slot can reference any entity, so a change can affect any device
        data = event.data
        if data["action"] != "update" or (
            data["changes"].keys() & _ENTITY_RESOLUTION_CHANGES
        ):
            cache.clear()

    hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _async_device_updated)
    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _async_entity_updated)
