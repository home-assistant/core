"""Types for the Google Tasks integration."""

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .api import AsyncConfigEntryAuth


@dataclass
class GoogleTasksData:
    """Class to hold Google Tasks data."""

    api: AsyncConfigEntryAuth
    task_lists: list[dict[str, Any]]


type GoogleTasksConfigEntry = ConfigEntry[GoogleTasksData]
