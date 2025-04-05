"""Common types and definitions."""

from homeassistant.config_entries import ConfigEntry

from .engine.engine import Engine

type LcConfigEntry = ConfigEntry[Engine]
