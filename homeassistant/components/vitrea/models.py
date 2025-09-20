"""Data models for Vitrea integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .client import VitreaClient
    from .cover import VitreaCover

type VitreaConfigEntry = ConfigEntry[VitreaRuntimeData]


@dataclass
class VitreaRuntimeData:
    """Runtime data for Vitrea integration."""

    client: VitreaClient
    covers: list[VitreaCover]
