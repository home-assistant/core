"""The Casper Glow integration models."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from .coordinator import CasperGlowCoordinator

type CasperGlowConfigEntry = ConfigEntry[CasperGlowCoordinator]
