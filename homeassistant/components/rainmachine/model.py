"""Define RainMachine data models."""
from dataclasses import dataclass


@dataclass
class RainMachineDescriptionMixinApiCategory:
    """Define an entity description mixin for binary and regular sensors."""

    api_category: str
    data_key: str


@dataclass
class RainMachineDescriptionMixinUid:
    """Define an entity description mixin for switches."""

    uid: int
