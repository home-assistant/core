"""Models for the Jellyfin integration."""
from __future__ import annotations

from dataclasses import dataclass

from jellyfin_apiclient_python import JellyfinClient

from .coordinator import JellyfinDataUpdateCoordinator


@dataclass
class JellyfinData:
    """Data for the Jellyfin integration."""

    client_device_id: str
    jellyfin_client: JellyfinClient
    coordinators: dict[str, JellyfinDataUpdateCoordinator]

    def get_device_ids(self) -> list[str]:
        """Fetch known device ids using session coordinator data."""
        if "sessions" not in self.coordinators:
            return []

        if self.coordinators["sessions"].data is None:
            return []

        return [
            session["DeviceId"]
            for session in self.coordinators["sessions"].data.values()
        ]
