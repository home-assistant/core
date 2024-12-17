"""Google Photos types."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import GooglePhotosUpdateCoordinator

type GooglePhotosConfigEntry = ConfigEntry[GooglePhotosUpdateCoordinator]
