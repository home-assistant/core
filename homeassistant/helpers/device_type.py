"""Helpers for device types and entity traits.

A device type says what a device is, for example an espresso machine. The
vocabulary of known device types is central and closed: it lives under
homeassistant/components/homeassistant/device_types/, where each type is a
definition and a strings file side by side and the path is the type.
Integrations pick a type that already exists, they never define their own.

Integrations declare a device type through `DeviceInfo` and map their entities
onto that type's traits in their own device_types.yaml. Traits are resolved on
demand from that mapping rather than stored on the entity registry entry, so
adding a trait to an integration needs no storage migration.

A trait carries two pieces of prose. `description` is written for language
models, lives in the definition and is not translated, matching every other LLM
facing string in Home Assistant. The display name is translated and is fetched
separately, because that is what Voice speaks and the frontend shows. A device
type and a trait may also carry translated aliases, extra spoken forms Assist
should match, such as "coffee machine" for an espresso machine.

API surface only; the implementation is not written yet.
"""

from dataclasses import dataclass

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

TRAIT_OPTIONS_NAMESPACE = "homeassistant"
TRAIT_OPTIONS_KEY = "trait"


@dataclass(frozen=True, slots=True)
class TraitSpec:
    """A single trait that a device type can be composed of."""

    trait: str
    description: str
    required: bool
    domains: frozenset[Platform]
    device_class: str | None


@dataclass(frozen=True, slots=True)
class DeviceTypeSpec:
    """A device type and the traits it is composed of."""

    device_type: str
    description: str
    traits: dict[str, TraitSpec]

    @property
    def required_traits(self) -> frozenset[str]:
        """Return the traits a device of this type is expected to provide."""
        raise NotImplementedError

    @property
    def optional_traits(self) -> frozenset[str]:
        """Return the traits a device of this type may provide."""
        raise NotImplementedError


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up trait resolution and device composition validation."""
    raise NotImplementedError


async def async_get_device_types(hass: HomeAssistant) -> dict[str, DeviceTypeSpec]:
    """Return the device type vocabulary, keyed by device type."""
    raise NotImplementedError


async def async_get_device_type_names(
    hass: HomeAssistant, device_type: str
) -> list[str]:
    """Return the translated name of a device type, followed by its voice aliases.

    Ordered so the first entry is the one to show or speak, mirroring
    `intent.async_get_entity_aliases`.
    """
    raise NotImplementedError


async def async_get_trait_names(
    hass: HomeAssistant, device_type: str, trait: str
) -> list[str]:
    """Return the translated name of a trait, followed by its voice aliases.

    The matching description is not translated and is read straight off the
    trait's `TraitSpec`.
    """
    raise NotImplementedError


@callback
def async_get_trait(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the trait an entity fills for its device.

    A trait set by the user takes precedence over the one its integration maps.
    """
    raise NotImplementedError


@callback
def async_get_entity_id(hass: HomeAssistant, device_id: str, trait: str) -> str | None:
    """Return the entity filling a trait on a device.

    The entity may belong to the device itself or to one of its child devices.
    """
    raise NotImplementedError


@callback
def async_get_traits(hass: HomeAssistant, device_id: str) -> dict[str, str]:
    """Return the traits a device provides, mapped to the entity filling each."""
    raise NotImplementedError


@callback
def async_set_trait(hass: HomeAssistant, entity_id: str, trait: str | None) -> None:
    """Override the trait of an entity, or pass None to fall back to the mapping."""
    raise NotImplementedError


@callback
def async_get_missing_traits(hass: HomeAssistant, device_id: str) -> frozenset[str]:
    """Return the required traits a device declares its type for but does not provide."""
    raise NotImplementedError
