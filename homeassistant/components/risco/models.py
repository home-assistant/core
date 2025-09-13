"""Models for Risco integration."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pyrisco import RiscoLocal


@dataclass
class LocalData:
    """A data class for local data passed to the platforms."""

    system: RiscoLocal
    partition_updates: dict[int, Callable[[], Any]] = field(default_factory=dict)
