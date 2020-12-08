import asyncio
import random
from pyamaha import AsyncDevice


class MusicCastDevice:
    """Dummy MusicCastDevice (device for HA) for Hello World example."""

    def __init__(self, client, ip):
        """Init dummy MusicCastDevice."""
        self.client = client
        self.ip = ip
        self.device = AsyncDevice(client, ip, self.handle)
        self._callbacks = set()

        print(f"HANDLE UDP ON {self.device._udp_port}")

    def handle(self, message):
        # update data...

        print()
        print("=== INCOMING UDP EVENT FROM MUSICCAST ===")
        print(message)
        print("=========================================")
        print()

        for callback in self._callbacks:
            callback()

    def register_callback(self, callback):
        """Register callback, called when MusicCastDevice changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)
