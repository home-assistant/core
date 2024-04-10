"""Base class for Ring entity."""

from collections.abc import Callable
from typing import Any, Concatenate, ParamSpec, TypeVar

from ring_doorbell import (
    AuthenticationError,
    RingDevices,
    RingError,
    RingGeneric,
    RingTimeout,
)

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import RingDataCoordinator, RingNotificationsCoordinator

_RingCoordinatorT = TypeVar(
    "_RingCoordinatorT",
    bound=(RingDataCoordinator | RingNotificationsCoordinator),
)
_RingBaseEntityT = TypeVar("_RingBaseEntityT", bound="RingBaseEntity[Any]")
_R = TypeVar("_R")
_P = ParamSpec("_P")


def exception_wrap(
    func: Callable[Concatenate[_RingBaseEntityT, _P], _R],
) -> Callable[Concatenate[_RingBaseEntityT, _P], _R]:
    """Define a wrapper to catch exceptions and raise HomeAssistant errors."""

    def _wrap(self: _RingBaseEntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
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


class RingBaseEntity(CoordinatorEntity[_RingCoordinatorT]):
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


class RingEntity(RingBaseEntity[RingDataCoordinator]):
    """Implementation for Ring devices."""

    def _get_coordinator_data(self) -> RingDevices:
        return self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        self._device = self._get_coordinator_data().get_device(
            self._device.device_api_id
        )
        super()._handle_coordinator_update()
