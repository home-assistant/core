"""Models helper class for the SleepIQ integration."""
import dataclasses

from .coordinator import SleepIQDataUpdateCoordinator


@dataclasses.dataclass
class SleepIQHassData:
    """Home Assistant SleepIQ runtime data."""

    coordinators: dict[str, SleepIQDataUpdateCoordinator] = dataclasses.field(
        default_factory=dict
    )
