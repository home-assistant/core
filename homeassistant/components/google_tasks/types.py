"""Types for the Google Tasks integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import TaskUpdateCoordinator


@dataclass
class GoogleTasksData:
    """Class to hold Google Tasks data."""

    coordinators: dict[str, TaskUpdateCoordinator]


type GoogleTasksConfigEntry = ConfigEntry[GoogleTasksData]
