"""The tplink integration models."""

from __future__ import annotations

from dataclasses import dataclass

from kasa import Credentials

from .coordinator import TPLinkDataUpdateCoordinator


@dataclass(slots=True)
class TPLinkData:
    """Data for the tplink integration."""

    parent_coordinator: TPLinkDataUpdateCoordinator
    children_coordinators: list[TPLinkDataUpdateCoordinator]
    camera_credentials: Credentials | None
    live_view: bool | None
