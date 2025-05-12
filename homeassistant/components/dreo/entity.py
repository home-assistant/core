"""Dreo device base entity."""

from functools import partial
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


class DreoEntity(CoordinatorEntity[DreoDataUpdateCoordinator]):
    """Representation of a base Dreo Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: dict[str, Any],
        coordinator: DreoDataUpdateCoordinator,
        unique_id_suffix: str | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize the Dreo entity."""

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
        """Call a device command handling error messages and update entity state."""

        try:
            await self.coordinator.hass.async_add_executor_job(
                partial(
                    self.coordinator.client.update_status, self._device_id, **kwargs
                )
            )
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
