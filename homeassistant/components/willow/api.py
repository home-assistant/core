"""Runtime data for the Willow integration."""

from dataclasses import dataclass

from .coordinator import WillowDataUpdateCoordinator, WillowProfile


@dataclass
class WillowRuntimeData:
    """Willow runtime data."""

    coordinator: WillowDataUpdateCoordinator
    profile: WillowProfile
