"""The bond integration models."""
from __future__ import annotations

from dataclasses import dataclass

from bond_async import BPUPSubscriptions

from .utils import BondHub


@dataclass
class BondData:
    """Data for the bond integration."""

    hub: BondHub
    bpup_subs: BPUPSubscriptions
