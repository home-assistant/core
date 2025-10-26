"""Types for Rain Bird integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyrainbird.async_client import AsyncRainbirdController
from pyrainbird.data import ModelAndVersion

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import (
        RainbirdScheduleUpdateCoordinator,
        RainbirdUpdateCoordinator,
    )


@dataclass
class RainbirdData:
    """Holder for shared integration data.

    The coordinators are lazy since they may only be used by some platforms when needed.
    """

    controller: AsyncRainbirdController
    model_info: ModelAndVersion
    coordinator: RainbirdUpdateCoordinator
    schedule_coordinator: RainbirdScheduleUpdateCoordinator


type RainbirdConfigEntry = ConfigEntry[RainbirdData]
