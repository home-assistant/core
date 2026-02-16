"""The Casper Glow integration models."""

from __future__ import annotations

from dataclasses import dataclass

from pycasperglow import CasperGlow

from homeassistant.config_entries import ConfigEntry

from .coordinator import CasperGlowCoordinator

type CasperGlowConfigEntry = ConfigEntry[CasperGlowData]


@dataclass(frozen=True)
class CasperGlowData:
    """Data for the Casper Glow integration."""

    coordinator: CasperGlowCoordinator

    @property
    def device(self) -> CasperGlow:
        """Return the CasperGlow device."""
        return self.coordinator.device
