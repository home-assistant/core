"""Models/Dataclasses for KNX integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, runtime_checkable

from .storage.const import CONF_DPT, CONF_GA_PASSIVE, CONF_GA_STATE, CONF_GA_WRITE

InstanceType_co = TypeVar("InstanceType_co", bound="Serializable", covariant=True)


@runtime_checkable
class Serializable(Protocol[InstanceType_co]):
    """A protocol that requires a class to implement methods for serialization and deserialization.

    Classes implementing this protocol must provide:
    - A class method `from_dict` to create an instance from a dictionary.
    - An instance method `to_dict` to serialize an object into a dictionary.
    """

    @classmethod
    def from_dict(cls: type[InstanceType_co], data: dict[str, Any]) -> InstanceType_co:
        """Create an instance of the class from a dictionary.

        Args:
            data (dict[str, Any]): The dictionary containing the serialized data.

        Returns:
            T: An instance of the class.

        """

    def to_dict(self) -> dict[str, Any]:
        """Serialize the current instance into a dictionary.

        Returns:
            dict[str, Any]: A dictionary representation of the instance.

        """


@dataclass
class ConfigGroup(Serializable["ConfigGroup"]):
    """Data class representing a configuration group."""

    properties: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert the instance into a dictionary."""
        return {
            prop: self.properties[prop].to_dict()
            if isinstance(self.properties[prop], Serializable)
            else self.properties[prop]
            for prop in self.properties
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfigGroup:
        """Create an instance from a dictionary."""
        return cls(
            properties={
                prop: GroupAddressConfig.from_dict(data[prop])
                if isinstance(data[prop], dict)
                else data[prop]
                for prop in data
            }
        )


@dataclass
class GroupAddressConfig(Serializable["GroupAddressConfig"]):
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


@dataclass
class PlatformConfig(Serializable["PlatformConfig"]):
    """Data class representing a platform configuration."""

    platform: str
    config: ConfigGroup

    def to_dict(self) -> dict[str, Any]:
        """Convert the instance into a dictionary."""
        return {
            "platform": self.platform,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlatformConfig:
        """Create an instance from a dictionary."""
        return cls(
            platform=data["platform"],
            config=data["config"],
        )
