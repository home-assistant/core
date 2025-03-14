"""Data structures for UniFi Access integration."""

from dataclasses import dataclass

from uiaccessclient import ApiClient

from . import UniFiAccessDoorCoordinator


@dataclass
class UniFiAccessData:
    """Data structure for UniFi Access integration."""

    api_client: ApiClient
    door_coordinator: UniFiAccessDoorCoordinator
