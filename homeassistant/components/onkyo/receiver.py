"""Onkyo receiver."""

from __future__ import annotations

from dataclasses import dataclass

import pyeiscp


@dataclass
class Receiver:
    """Onkyo receiver."""

    conn: pyeiscp.Connection
    model_name: str
    identifier: str
    name: str
    discovered: bool


@dataclass
class ReceiverInfo:
    """Onkyo receiver information."""

    host: str
    port: int
    model_name: str
    identifier: str
