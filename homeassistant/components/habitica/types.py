"""Types for Habitica integration."""

from enum import StrEnum

from homeassistant.config_entries import ConfigEntry

from .coordinator import HabiticaDataUpdateCoordinator

type HabiticaConfigEntry = ConfigEntry[HabiticaDataUpdateCoordinator]


class HabiticaTaskType(StrEnum):
    """Habitica Entities."""

    HABIT = "habit"
    DAILY = "daily"
    TODO = "todo"
    REWARD = "reward"
