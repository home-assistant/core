"""Support for Velbus devices."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar

from velbusaio.channels import Channel as VelbusChannel

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class VelbusEntity(Entity):
    """Representation of a Velbus entity."""

    _attr_should_poll: bool = False

    def __init__(self, channel: VelbusChannel) -> None:
        """Initialize a Velbus entity."""
        self._channel = channel
        self._attr_name = channel.get_name()
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, str(channel.get_module_address())),
            },
            manufacturer="Velleman",
            model=channel.get_module_type_name(),
            name=channel.get_full_name(),
            sw_version=channel.get_module_sw_version(),
        )
        serial = channel.get_module_serial() or str(channel.get_module_address())
        self._attr_unique_id = f"{serial}-{channel.get_channel_number()}"

    async def async_added_to_hass(self) -> None:
        """Add listener for state changes."""
        self._channel.on_status_update(self._on_update)

    async def _on_update(self) -> None:
        self.async_write_ha_state()


_T = TypeVar("_T", bound="VelbusEntity")
_P = ParamSpec("_P")


def api_call(
    func: Callable[Concatenate[_T, _P], Awaitable[None]]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Catch command exceptions."""

    @wraps(func)
    async def cmd_wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(self, *args, **kwargs)
        except OSError as exc:
            raise HomeAssistantError(
                f"Could not execute {func.__name__} service for {self.name}"
            ) from exc

    return cmd_wrapper
