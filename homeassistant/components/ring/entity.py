"""Base class for Ring entity."""

from collections.abc import Callable
from typing import Any, Concatenate, ParamSpec, TypeVar

from ring_doorbell import AuthenticationError, RingError, RingGeneric, RingTimeout

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import (
    RingDataCoordinator,
    RingDeviceData,
    RingNotificationsCoordinator,
)

_RingCoordinatorT = TypeVar(
    "_RingCoordinatorT",
    bound=(RingDataCoordinator | RingNotificationsCoordinator),
)
_T = TypeVar("_T", bound="RingEntity")
_P = ParamSpec("_P")


def exception_wrap(
    func: Callable[Concatenate[_T, _P], Any],
) -> Callable[Concatenate[_T, _P], Any]:
    """Define a wrapper to catch exceptions and raise HomeAssistant errors."""

    def _wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            return func(self, *args, **kwargs)
        except AuthenticationError as err:
            self.hass.loop.call_soon_threadsafe(
                self.coordinator.config_entry.async_start_reauth, self.hass
            )
            raise HomeAssistantError(err) from err
        except RingTimeout as err:
            raise HomeAssistantError(
                f"Timeout communicating with API {func}: {err}"
            ) from err
        except RingError as err:
            raise HomeAssistantError(
                f"Error communicating with API{func}: {err}"
            ) from err

    return _wrap


class RingEntity(CoordinatorEntity[_RingCoordinatorT]):
    """Base implementation for Ring device."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: RingGeneric,
        coordinator: _RingCoordinatorT,
    ) -> None:
        """Initialize a sensor for Ring device."""
        super().__init__(coordinator, context=device.id)
        self._device = device
        self._attr_extra_state_attributes = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},  # device_id is the mac
            manufacturer="Ring",
            model=device.model,
            name=device.name,
        )

    def _get_coordinator_device_data(self) -> RingDeviceData | None:
        if (data := self.coordinator.data) and (
            device_data := data.get(self._device.id)
        ):
            return device_data
        return None

    def _get_coordinator_device(self) -> RingGeneric | None:
        if (device_data := self._get_coordinator_device_data()) and (
            device := device_data.device
        ):
            return device
        return None

    def _get_coordinator_history(self) -> list | None:
        if (device_data := self._get_coordinator_device_data()) and (
            history := device_data.history
        ):
            return history
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        if device := self._get_coordinator_device():
            self._device = device
        super()._handle_coordinator_update()
