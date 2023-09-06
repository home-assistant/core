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
