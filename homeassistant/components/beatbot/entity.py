"""Shared base entity for all Beatbot platforms.

Every entity attached to a device contributes the same `device_info`
(name / manufacturer / model / sw_version) to the device registry, instead
of relying on a single entity (the vacuum) to supply it. That way the
device is populated correctly no matter which platform's entities load
first or fail to load.
"""

from collections.abc import Awaitable, Callable
from typing import Any, override

from beatbot_cloud import BeatbotAuthenticationError, BeatbotConnectionError

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BeatbotCoordinator
from .iot.const import DOMAIN
from .models import BeatbotDeviceData


class BeatbotEntity(CoordinatorEntity[BeatbotCoordinator]):
    """Common base: device metadata + per-device data accessor."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: BeatbotCoordinator, device_id: str) -> None:
        """Initialize a Beatbot entity."""
        super().__init__(coordinator)
        self._device_id = device_id

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
            if self.coordinator.config_entry is not None:
                self.coordinator.config_entry.async_start_reauth(self.hass)
            raise ConfigEntryAuthFailed from err
        except BeatbotConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_connection_error",
                translation_placeholders={
                    "device": self.data.name or self._device_id,
                },
            ) from err

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self.data.name or None,
            manufacturer="Beatbot",
            model=self.data.model or None,
            model_id=self.data.product_id,
            # Show each firmware channel's version distinctly (e.g.
            # "ch1:0.0.80 ch2:0.0.80") rather than collapsing to one value.
            sw_version=" ".join(
                f"ch{v.channel}:{v.version}" for v in self.data.versions if v.version
            )
            or None,
        )
