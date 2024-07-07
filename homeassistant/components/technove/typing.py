"""Typings for the TechnoVE integration."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import TechnoVEDataUpdateCoordinator

TechnoVEConfigEntry = ConfigEntry[TechnoVEDataUpdateCoordinator]
