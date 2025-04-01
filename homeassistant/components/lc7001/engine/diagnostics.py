"""A BroadcastMemory packet."""

from typing import Any

from .packet import Packet


class BroadcastMemory(Packet):
    """A BroadcastMemory packet."""

    _service_name = "BroadcastMemory"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a BroadcastMemory packet."""
        super().__init__(**kwargs)

        self.FreeMemory = kwargs.get("FreeMemory")
        self.FreeMemLowWater = kwargs.get("FreeMemLowWater")
        self.Malloc_Count = kwargs.get("Malloc_Count")
        self.Free_Count = kwargs.get("Free_Count")
        self.JsonConnections = kwargs.get("JsonConnections")
        self.StaticRamUsage = kwargs.get("StaticRamUsage")
        self.PeakRamUsage = kwargs.get("PeakRamUsage")
        self.CurrentTime = kwargs.get("CurrentTime")
        self.uSec = kwargs.get("uSec")
        self.Seqno = kwargs.get("Seqno")
