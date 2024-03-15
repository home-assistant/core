"""Common code for tplink."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar
import logging

from kasa import (
    AuthenticationException,
    SmartDevice,
    SmartDeviceException,
    TimeoutException,
)

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator

_T = TypeVar("_T", bound="CoordinatedTPLinkEntity")
_P = ParamSpec("_P")


_LOGGER = logging.getLogger(__name__)

def async_refresh_after(
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to raise HA errors and refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except AuthenticationException as ex:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_authentication",
                translation_placeholders={
                    "func": func.__name__,
                    "exc": str(ex),
                },
            ) from ex
        except TimeoutException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_timeout",
                translation_placeholders={
                    "func": func.__name__,
                    "exc": str(ex),
                },
            ) from ex
        except SmartDeviceException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_error",
                translation_placeholders={
                    "func": func.__name__,
                    "exc": str(ex),
                },
            ) from ex
        await self.coordinator.async_request_refresh()

    return _async_wrap


class CoordinatedTPLinkEntity(CoordinatorEntity[TPLinkDataUpdateCoordinator], ABC):
    """Common base class for all coordinated tplink entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        parent: SmartDevice = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device: SmartDevice = device
        self._attr_unique_id = device.device_id
        self._attr_device_info = DeviceInfo(
            # TODO: find out if connections have any use and/or if it should
            #  still be set for the main device. if set for child devices, all
            #  devices will be presented by a single device
            # connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
            identifiers={(DOMAIN, str(device.device_id))},
            manufacturer="TP-Link",
            model=device.model,
            name=device.alias,
            sw_version=device.hw_info["sw_ver"],
            hw_version=device.hw_info["hw_ver"],
        )

        if parent is not None:
            self._attr_device_info["via_device"] = (DOMAIN, parent.device_id)

    @abstractmethod
    def _async_update_attrs(self):
        """Callback to update the entity internals."""
        raise NotImplementedError()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._async_update_attrs()
            self._attr_available = True
        except Exception as ex:
            _LOGGER.warning("Unable to read data for %s: %s", self.entity_description, ex)
            self._attr_available = False

        super()._handle_coordinator_update()
