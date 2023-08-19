"""Support for Velbus devices."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar

from duotecno.unit import BaseUnit

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class DuotecnoEntity(Entity):
    """Representation of a Duotecno entity."""

    _attr_should_poll: bool = False
    _unit: BaseUnit

    def __init__(self, unit) -> None:
        """Initialize a Duotecno entity."""
        self._unit = unit
        self._attr_name = unit.get_name()
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, str(unit.get_node_address())),
            },
            manufacturer="Duotecno",
            name=unit.get_node_name(),
        )
        self._attr_unique_id = f"{unit.get_node_address()}-{unit.get_number()}"

    async def async_added_to_hass(self) -> None:
        """When added to hass."""
        self._unit.on_status_update(self._on_update)

    async def _on_update(self) -> None:
        """When a unit has an update."""
        self.async_write_ha_state()


_T = TypeVar("_T", bound="DuotecnoEntity")
_P = ParamSpec("_P")


def cmd(
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
                f"Error calling {func.__name__} on entity {self.entity_id},"
                f" packet transmit failed"
            ) from exc

    return cmd_wrapper
