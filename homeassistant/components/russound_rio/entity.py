"""Base entity for Russound RIO integration."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aiorussound import Controller

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, RUSSOUND_RIO_EXCEPTIONS


def command[_EntityT: RussoundBaseEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Awaitable[None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Wrap async calls to raise on request error."""

    @wraps(func)
    async def decorator(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(self, *args, **kwargs)
        except RUSSOUND_RIO_EXCEPTIONS as exc:
            raise HomeAssistantError(
                f"Error executing {func.__name__} on entity {self.entity_id},"
            ) from exc

    return decorator


class RussoundBaseEntity(Entity):
    """Russound Base Entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        controller: Controller,
    ) -> None:
        """Initialize the entity."""
        self._instance = controller.instance
        self._controller = controller
        self._primary_mac_address = (
            controller.mac_address or controller.parent_controller.mac_address
        )
        self._device_identifier = (
            self._controller.mac_address
            or f"{self._primary_mac_address}-{self._controller.controller_id}"
        )
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{self._instance.host}",
            # Use MAC address of Russound device as identifier
            identifiers={(DOMAIN, self._device_identifier)},
            manufacturer="Russound",
            name=controller.controller_type,
            model=controller.controller_type,
            sw_version=controller.firmware_version,
        )
        if controller.parent_controller:
            self._attr_device_info["via_device"] = (
                DOMAIN,
                controller.parent_controller.mac_address,
            )
        else:
            self._attr_device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, controller.mac_address)
            }

    @callback
    def _is_connected_updated(self, connected: bool) -> None:
        """Update the state when the device is ready to receive commands or is unavailable."""
        self._attr_available = connected
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._instance.add_connection_callback(self._is_connected_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        self._instance.remove_connection_callback(self._is_connected_updated)
