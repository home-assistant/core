"""Common code for tplink."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Coroutine
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from kasa import (
    AuthenticationException,
    Feature,
    SmartDevice,
    SmartDeviceException,
    TimeoutException,
)

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import legacy_device_id
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
        feature: Feature = None,
        parent: SmartDevice = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device: SmartDevice = device
        self._device = device  # TODO: duplicate device.
        if feature is None:
            self._attr_unique_id = legacy_device_id(device)
            _LOGGER.warning("Got empty feature: %s %s", self, type(self))
        else:
            self._attr_unique_id = f"{legacy_device_id(device)}_new_{feature.id}"
            self._attr_entity_category = self._category_for_feature(feature)
        self._feature = feature

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

    def _category_for_feature(self, feature: Feature):
        match feature.category:
            case Feature.Category.Primary:  # Main controls have no category
                return None
            case Feature.Category.Info:
                return None
            case Feature.Category.Debug:
                return EntityCategory.DIAGNOSTIC
            case Feature.Category.Config:
                return EntityCategory.CONFIG

    @abstractmethod
    def _async_update_attrs(self):
        """Implement to update the entity internals."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._async_update_attrs()
            self._attr_available = True
        except Exception as ex:
            _LOGGER.warning(
                "Unable to read data for %s %s: %s",
                self.device,
                self.entity_description,
                ex,
            )
            self._attr_available = False

        super()._handle_coordinator_update()
