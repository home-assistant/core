"""The Screenlogic integration."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import ScreenlogicDataUpdateCoordinator

type ScreenLogicConfigEntry = ConfigEntry[ScreenlogicDataUpdateCoordinator]
