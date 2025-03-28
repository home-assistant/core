"""A BroadcastMemory packet."""

from .packet import Packet


class BroadcastMemory(Packet):
    """A BroadcastMemory packet."""

    def __init__(self, Service: str | None = None, **kwargs) -> None:
        """Initialize a BroadcastMemory packet."""
        super().__init__(Service=Service or "BroadcastMemory", **kwargs)

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
