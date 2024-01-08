"""Define RainMachine data models."""
from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription


@dataclass(frozen=True)
class RainMachineEntityDescriptionMixinApiCategory:
    """Define an entity description mixin to include an API category."""

    api_category: str


@dataclass(frozen=True)
class RainMachineEntityDescriptionMixinDataKey:
    """Define an entity description mixin to include a data payload key."""

    data_key: str


@dataclass(frozen=True)
class RainMachineEntityDescriptionMixinUid:
    """Define an entity description mixin to include an activity UID."""

    uid: int


@dataclass(frozen=True)
class RainMachineEntityDescription(
    EntityDescription, RainMachineEntityDescriptionMixinApiCategory
):
    """Describe a RainMachine entity."""
