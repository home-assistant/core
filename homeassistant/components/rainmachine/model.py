"""Define RainMachine data models."""
from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription


@dataclass
class RainMachineEntityDescriptionMixinApiCategory:
    """Define an entity description mixin to include an API category."""

    api_category: str


@dataclass
class RainMachineEntityDescriptionMixinDataKey:
    """Define an entity description mixin to include a data payload key."""

    data_key: str


@dataclass
class RainMachineEntityDescriptionMixinUid:
    """Define an entity description mixin to include an activity UID."""

    uid: int


@dataclass
class RainMachineEntityDescription(
    EntityDescription, RainMachineEntityDescriptionMixinApiCategory
):
    """Describe a RainMachine entity."""
