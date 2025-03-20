"""The baf integration models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BAFDiscovery:
    """A BAF Discovery."""

    ip_address: str
    name: str
    uuid: str
    model: str
