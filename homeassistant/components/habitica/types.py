"""Types for Habitica integration."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import HabiticaDataUpdateCoordinator

type HabiticaConfigEntry = ConfigEntry[HabiticaDataUpdateCoordinator]
