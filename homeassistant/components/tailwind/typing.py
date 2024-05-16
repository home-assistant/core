"""Typings for the Tailwind integration."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import TailwindDataUpdateCoordinator

TailwindConfigEntry = ConfigEntry[TailwindDataUpdateCoordinator]
