"""Dreo device base entity."""

from functools import partial
import logging
from typing import Any

from hscloud.hscloudexception import (
    HsCloudAccessDeniedException,
    HsCloudBusinessException,
    HsCloudException,
    HsCloudFlowControlException,
)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DreoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class DreoEntity(CoordinatorEntity[DreoDataUpdateCoordinator]):
    """Representation of a base Dreo Entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
        unique_id_suffix: str | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize the Dreo entity.

        Args:
            device: Device information dictionary
            coordinator: The Dreo DataUpdateCoordinator
            unique_id_suffix: Optional suffix for unique_id to differentiate multiple entities from same device
            name: Optional entity name, None will use the device name as-is

        """
        super().__init__(coordinator)
        self._device_id = device.get("deviceSn")
        self._model = device.get("model")
        self._attr_name = name

        if unique_id_suffix:
            self._attr_unique_id = f"{self._device_id}_{unique_id_suffix}"
        else:
            self._attr_unique_id = self._device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer="Dreo",
            model=self._model,
            name=device.get("deviceName"),
            sw_version=device.get("moduleFirmwareVersion"),
            hw_version=device.get("mcuFirmwareVersion"),
        )

    async def async_send_command_and_update(
        self, translation_key: str, **kwargs: Any
    ) -> None:
        """Call a device command handling error messages and update entity state.

        Args:
            translation_key: Translation key for error message
            kwargs: Keyword arguments for the update_status function

        Returns:
            None

        """
        try:
            await self.coordinator.hass.async_add_executor_job(
                partial(
                    self.coordinator.client.update_status, self._device_id, **kwargs
                )
            )
            # Force immediate refresh of device state
            # The coordinator will automatically update all registered entities
            await self.coordinator.async_refresh()
        except (
            HsCloudException,
            HsCloudBusinessException,
            HsCloudAccessDeniedException,
            HsCloudFlowControlException,
        ) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=translation_key
            ) from ex
