"""Shared base entity for all Beatbot platforms.

Every entity attached to a device contributes the same `device_info`
(name / manufacturer / model / sw_version) to the device registry, instead
of relying on a single entity (the vacuum) to supply it. That way the
device is populated correctly no matter which platform's entities load
first or fail to load.
"""

from typing import Any, override

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BeatbotAuthError, BeatbotConnectionError
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

    async def _async_send_command(self, coro: Any) -> None:
        """Run a control API call with HA-idiomatic error translation.

        - Auth failure escalates to ConfigEntryAuthFailed so HA triggers the
          reauth flow — consistent with the coordinator's poll path. A raw
          BeatbotAuthError from a service call would otherwise just fail the
          call with no prompt to re-login.
        - Connection/transport failure surfaces as HomeAssistantError so the
          user sees a readable message instead of an opaque stack.

        No retry: the backend returns a synchronous Result envelope, so a
        failed request means the action likely did not apply (or the response
        was lost). Blindly retrying toggle-semantics actions (start/pause)
        risks double execution. State reconciliation is left to the
        post-control refresh and the 30s poll.
        """
        if not self.data.is_online:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_offline",
                translation_placeholders={
                    "device": self.data.name or self._device_id,
                },
            )
        try:
            await coro
        except BeatbotAuthError as err:
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
            model=self.data.product_id,
            # Show each firmware channel's version distinctly (e.g.
            # "ch1:0.0.80 ch2:0.0.80") rather than collapsing to one value.
            sw_version=" ".join(
                f"ch{v.channel}:{v.version}" for v in self.data.versions if v.version
            )
            or None,
        )
