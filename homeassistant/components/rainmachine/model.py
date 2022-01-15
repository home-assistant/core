"""Define RainMachine data models."""
from dataclasses import dataclass


@dataclass
class RainMachineSensorDescriptionMixin:
    """Define an entity description mixin for binary and regular sensors."""

    api_category: str
