"""Base entity for Liebherr integration."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from pyliebherrhomeapi import (
    LiebherrConnectionError,
    LiebherrTimeoutError,
    TemperatureControl,
    ZonePosition,
)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, REFRESH_DELAY
from .coordinator import LiebherrCoordinator

# Zone position to translation key mapping
ZONE_POSITION_MAP = {
    ZonePosition.TOP: "top_zone",
    ZonePosition.MIDDLE: "middle_zone",
    ZonePosition.BOTTOM: "bottom_zone",
}


class LiebherrEntity(CoordinatorEntity[LiebherrCoordinator]):
    """Base entity for Liebherr devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
    ) -> None:
        """Initialize the Liebherr entity."""
        super().__init__(coordinator)

        device = coordinator.data.device

        model = None
        if device.device_type:
            model = device.device_type.title()

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=device.nickname or device.device_name,
            manufacturer=MANUFACTURER,
            model=model,
            model_id=device.device_name,
        )

    async def _async_send_command(
        self,
        command: Coroutine[Any, Any, None],
    ) -> None:
        """Send a command with error handling and delayed refresh."""
        try:
            await command
        except (LiebherrConnectionError, LiebherrTimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err

        await asyncio.sleep(REFRESH_DELAY.total_seconds())
        await self.coordinator.async_request_refresh()


class LiebherrZoneEntity(LiebherrEntity):
    """Base entity for zone-based Liebherr entities.

    This class should be used for entities that are associated with a specific
    temperature control zone (e.g., climate, zone sensors).
    """

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        zone_id: int,
    ) -> None:
        """Initialize the zone entity."""
        super().__init__(coordinator)
        self._zone_id = zone_id

    @property
    def temperature_control(self) -> TemperatureControl | None:
        """Get the temperature control for this zone."""
        return self.coordinator.data.get_temperature_controls().get(self._zone_id)

    def _get_zone_translation_key(self) -> str | None:
        """Get the translation key for this zone."""
        control = self.temperature_control
        if control and isinstance(control.zone_position, ZonePosition):
            return ZONE_POSITION_MAP.get(control.zone_position)
        # Fallback to None to use device model name
        return None
