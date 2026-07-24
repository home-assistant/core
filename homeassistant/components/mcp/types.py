"""Types for the Model Context Protocol integration."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import ModelContextProtocolCoordinator

type ModelContextProtocolConfigEntry = ConfigEntry[ModelContextProtocolCoordinator]
