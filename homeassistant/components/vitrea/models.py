"""Data models for Vitrea integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import VitreaCoordinator

type VitreaConfigEntry = ConfigEntry[VitreaCoordinator]
