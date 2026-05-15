"""Compatibility helpers for Home Assistant infrared command objects."""

from collections.abc import Iterable
import importlib
from typing import Protocol


class _InfraredProtocolsCommand:
    """Fallback command symbol for HA infrared imports.

    Some infrared_protocols releases no longer expose Command at package root,
    while Home Assistant versions using the infrared platform still import it
    from there during module import. The integration only needs this symbol to
    let HA's infrared module import successfully; command objects are handled
    structurally via the InfraredCommand protocol below.
    """


def _ensure_infrared_protocols_command() -> None:
    """Ensure Home Assistant can import infrared_protocols.Command."""
    try:
        infrared_protocols = importlib.import_module("infrared_protocols")
    except ImportError:
        return

    if not hasattr(infrared_protocols, "Command"):
        setattr(infrared_protocols, "Command", _InfraredProtocolsCommand)


_ensure_infrared_protocols_command()


class RawTiming(Protocol):
    """Protocol for a single raw infrared timing pair."""

    high_us: int
    low_us: int


class InfraredCommand(Protocol):
    """Protocol for infrared commands accepted by Home Assistant."""

    modulation: int | str

    def get_raw_timings(self) -> Iterable[RawTiming]:
        """Return raw infrared timing pairs."""
