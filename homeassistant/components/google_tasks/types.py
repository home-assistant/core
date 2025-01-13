"""Types for the Google Tasks integration."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import TaskUpdateCoordinator

type GoogleTasksConfigEntry = ConfigEntry[list[TaskUpdateCoordinator]]
