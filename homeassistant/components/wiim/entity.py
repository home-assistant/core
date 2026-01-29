# homeassistant/components/wiim/entity.py
"""Base entity for the WiiM integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from wiim.exceptions import WiimDeviceException, WiimException, WiimRequestException
from wiim.wiim_device import WiimDevice

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SDK_LOGGER


def exception_wrap[_WiimEntityT: WiimBaseEntity, **_P, _R](
    func: Callable[Concatenate[_WiimEntityT, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[_WiimEntityT, _P], Coroutine[Any, Any, _R]]:
    """Define a wrapper to catch SDK exceptions and raise HomeAssistant errors."""

    async def _wrap(self: _WiimEntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except WiimRequestException as err:
            SDK_LOGGER.warning("HTTP API error for %s: %s", self.entity_id, err)
            raise WiimException(
                f"HTTP API not available for action {self.entity_description.key}"
            ) from err
        except WiimDeviceException as err:
            SDK_LOGGER.warning(
                "Device communication error for %s: %s", self.entity_id, err
            )
            raise WiimException(
                f"HTTP API not available for action {self.entity_description.key}"
            ) from err
        except WiimException as err:
            SDK_LOGGER.warning("An SDK error occurred for %s: %s", self.entity_id, err)
            raise HomeAssistantError(
                f"An error occurred with WiiM device {self._device.name}: {err}"
            ) from err

    return _wrap


class WiimBaseEntity(Entity):
    """Base representation of a WiiM entity."""

    _attr_has_entity_name = True

    def __init__(self, wiim_device: WiimDevice) -> None:
        """Initialize the WiiM base entity."""
        self._device = wiim_device
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, self._device.udn)},
            name=self._device.name,
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            sw_version=self._device.firmware_version,
        )
        if self._device.upnp_device and self._device.upnp_device.presentation_url:
            self._attr_device_info["configuration_url"] = (
                self._device.upnp_device.presentation_url
            )
        elif self._device.http_api_url:
            self._attr_device_info["configuration_url"] = self._device.http_api_url

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.available
