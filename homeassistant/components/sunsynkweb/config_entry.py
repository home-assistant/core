"""Placeholder for config entry type - avoids circular references."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import SunsynkUpdateCoordinator

type SunsynkConfigEntry = ConfigEntry[SunsynkUpdateCoordinator]
