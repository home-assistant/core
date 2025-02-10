"""Models/Dataclasses for KNX integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Self, runtime_checkable

from .storage.const import CONF_DPT, CONF_GA_PASSIVE, CONF_GA_STATE, CONF_GA_WRITE


@runtime_checkable
class Serializable(Protocol):
    """A protocol that defines the interface for serializable classes.

    Classes that implement this protocol can be serialized to and from dictionaries.
    """

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct an instance of the class from a dictionary.

        Args:
            data (dict[str, Any]): A dictionary containing the data to construct the instance.

        Returns:
            Self: An instance of the class.

        """

    def to_dict(self) -> dict[str, Any]:
        """Serialize the instance to a dictionary.

        Returns:
            dict[str, Any]: A dictionary representation of the instance.

        """


@dataclass
class GroupAddressConfig(Serializable):
    """Data class representing a KNX group address configuration."""

    write_ga: str | int | None
    state_ga: str | int | None
    passive_ga: list[str | int] | None
    dpt: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert the instance into a dictionary."""
        return {
            CONF_GA_WRITE: self.write_ga,
            CONF_GA_STATE: self.state_ga,
            CONF_GA_PASSIVE: self.passive_ga,
            CONF_DPT: self.dpt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroupAddressConfig:
        """Create an instance from a dictionary."""
        return cls(
            write_ga=data.get(CONF_GA_WRITE),
            state_ga=data.get(CONF_GA_STATE),
            passive_ga=data.get(CONF_GA_PASSIVE),
            dpt=data.get(CONF_DPT),
        )
