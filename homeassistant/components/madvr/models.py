"""Runtime models for madVR Envy integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from madvr_envy import MadvrEnvyClient

from .coordinator import MadvrEnvyCoordinator


@dataclass(slots=True)
class MadvrEnvyRuntimeData:
    """Stored runtime state for a config entry."""

    client: MadvrEnvyClient
    coordinator: MadvrEnvyCoordinator
    last_data: dict[str, Any]
