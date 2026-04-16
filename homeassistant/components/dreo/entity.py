"""Dreo device base entity."""

import asyncio
from functools import partial
from typing import Any

from pydreo import (
    DreoAccessDeniedException,
    DreoBusinessException,
    DreoException,
    DreoFlowControlException,
)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DreoDataUpdateCoordinator

AFTER_COMMAND_REFRESH = 1


class DreoEntity(CoordinatorEntity[DreoDataUpdateCoordinator]):
    """Representation of a base Dreo Entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DreoDataUpdateCoordinator) -> None:
        """Initialize the Dreo entity."""

        super().__init__(coordinator)
        device = coordinator.device
        self._client = coordinator.client
        self._device_id = coordinator.device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Dreo",
            model=device.get("model"),
            name=device.get("deviceName"),
            serial_number=self._device_id,
            sw_version=device.get("moduleFirmwareVersion"),
            hw_version=device.get("mcuFirmwareVersion"),
        )

    async def async_send_command(
        self, error_translation_key: str, **kwargs: Any
    ) -> None:
        """Call a device command and handle errors."""

        try:
            await self.coordinator.hass.async_add_executor_job(
                partial(self._client.update_status, self._device_id, **kwargs)
            )
        except (
            DreoException,
            DreoBusinessException,
            DreoAccessDeniedException,
            DreoFlowControlException,
        ) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=error_translation_key
            ) from ex

        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_refresh()
