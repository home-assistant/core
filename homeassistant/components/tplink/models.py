"""The tplink integration models."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import TPLinkDataUpdateCoordinator


@dataclass(slots=True)
class TPLinkData:
    """Data for the tplink integration."""

    parent_coordinator: TPLinkDataUpdateCoordinator
    children_coordinators: list[TPLinkDataUpdateCoordinator]
