"""Base Entity for Frontier Silicon Devices (Medion, Hama, Auna,...)."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from afsapi import AFSAPI, FSApiError, FSConnectionError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import FrontierSiliconConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def fs_command_exception_wrap[
    _AFSAPIDeviceT: FrontierSiliconEntity,
    **_P,
    _R,
](
    func: Callable[Concatenate[_AFSAPIDeviceT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_AFSAPIDeviceT, _P], Coroutine[Any, Any, _R]]:
    """Wrap command methods and map API exceptions to HA errors."""

    @wraps(func)
    async def _wrap(self: _AFSAPIDeviceT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except FSConnectionError as err:
            command = func.__name__.removeprefix("async_")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"command": command},
            ) from err
        except FSApiError as err:
            command = func.__name__.removeprefix("async_")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"command": command, "message": str(err)},
            ) from err

    return _wrap


class FrontierSiliconEntity(Entity):
    """Defines a base Frontier Silicon entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        afsapi: AFSAPI,
        entry: FrontierSiliconConfigEntry,
    ) -> None:
        """Initialize the Frontier Silicon entity."""
        self._entry = entry
        self.fs_device = afsapi

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )
        self._attr_unique_id = entry.entry_id

    async def async_update(self) -> None:
        """Update Frontier Silicon entity."""
        if not self.enabled:
            return

        try:
            await self._fs_update()
            if not self.available:
                _LOGGER.warning(
                    "Reconnected to %s",
                    self.name or self.fs_device.webfsapi_endpoint,
                )
                self._attr_available = True
        except FSConnectionError:
            if self.available:
                _LOGGER.warning(
                    "Could not connect to %s. Did it go offline?",
                    self.name or self.fs_device.webfsapi_endpoint,
                )
                self._attr_available = False

    async def _fs_update(self) -> None:
        """Update Frontier Silicon entity."""
        raise NotImplementedError
