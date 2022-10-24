"""The OralB integration models."""

from __future__ import annotations

from dataclasses import dataclass

from oralb import OralB

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class OralBData:
    """Data for the OralB integration."""

    device: OralB
    coordinator: DataUpdateCoordinator
