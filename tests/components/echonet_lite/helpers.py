"""Utilities shared across ECHONET Lite integration tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TestProperty:
    """Minimal representation of an ECHONET Lite property."""

    __test__ = False
    epc: int
    edt: bytes


@dataclass(slots=True)
class TestFrame:
    """Minimal representation of an ECHONET Lite frame."""

    __test__ = False
    tid: int
    seoj: bytes
    deoj: bytes
    esv: int
    properties: list[TestProperty]

    def is_response_frame(self) -> bool:
        """Check if frame is a response (success or failure)."""
        return (0x70 <= self.esv <= 0x7F) or (0x50 <= self.esv <= 0x5F)
