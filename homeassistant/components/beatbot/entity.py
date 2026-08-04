"""Shared base entity for the Beatbot integration."""

from collections.abc import Awaitable, Callable
from typing import Any

from beatbot_cloud import (
    BeatbotAuthenticationError,
    BeatbotConnectionError,
    BeatbotDeviceData,
)

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BeatbotCoordinator


class BeatbotEntity(CoordinatorEntity[BeatbotCoordinator]):
    """Common base: device metadata + per-device data accessor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BeatbotCoordinator, device_id: str) -> None:
        """Initialize a Beatbot entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        data = self.data
        version = next((item.version for item in data.versions if item.version), None)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=data.name or None,
            manufacturer="Beatbot",
            model=data.model or None,
            model_id=data.product_id,
            sw_version=version,
        )

    @property
    def data(self) -> BeatbotDeviceData:
        """Return the latest data for this device."""
        return self.coordinator.data[self._device_id]

    async def _async_send_command(self, command: Callable[[], Awaitable[Any]]) -> None:
        """Run without retrying and translate library errors for Home Assistant."""
        if not self.data.is_online:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_offline",
                translation_placeholders={
                    "device": self.data.name or self._device_id,
                },
            )
        try:
            await command()
        except BeatbotAuthenticationError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except BeatbotConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_connection_error",
                translation_placeholders={
                    "device": self.data.name or self._device_id,
                },
            ) from err
