"""Type definitions for the TuneBlade Remote integration.

This module defines runtime data structures used by the TuneBlade Remote integration.
"""

from typing import TypedDict

from .coordinator import TuneBladeDataUpdateCoordinator


class TuneBladeRuntimeData(TypedDict):
    """Runtime data stored for the TuneBlade Remote integration."""

    coordinator: TuneBladeDataUpdateCoordinator
