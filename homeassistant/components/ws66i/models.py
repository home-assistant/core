"""The ws66i integration models."""
from __future__ import annotations

from dataclasses import dataclass

from pyws66i import WS66i

from .coordinator import Ws66iDataUpdateCoordinator


@dataclass
class SourceRep:
    """Different representations of the amp sources."""

    id_name: dict[int, str]
    name_id: dict[str, int]
    name_list: list[str]


@dataclass
class Ws66iData:
    """Data for the ws66i integration."""

    host_ip: str
    device: WS66i
    sources: SourceRep
    coordinator: Ws66iDataUpdateCoordinator
    zones: list[int]
