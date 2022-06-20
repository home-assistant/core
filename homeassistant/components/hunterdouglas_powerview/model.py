"""Define Hunter Douglas data models."""
from typing import Any

from aiopvapi.helpers.aiorequest import AioRequest

from .coordinator import PowerviewShadeUpdateCoordinator


class PowerviewEntry:
    """Define class for main domain information."""

    def __init__(
        self,
        api: AioRequest,
        room_data: dict[str, Any],
        scene_data: dict[str, Any],
        shades,
        shade_data: dict[str, Any],
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific SmartPlug."""
        self.api: AioRequest = api
        self.room_data: dict[str, Any] = room_data
        self.scene_data: dict[str, Any] = scene_data
        self.shades = shades
        self.shade_data: dict[str, Any] = shade_data
        self.coordinator: PowerviewShadeUpdateCoordinator = coordinator
        self.device_info: dict[str, Any] = device_info
