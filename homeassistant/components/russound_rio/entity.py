"""Base entity for Russound RIO integration."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aiorussound import Controller, RussoundClient, RussoundTcpConnectionHandler
from aiorussound.models import CallbackType

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
        self._client = controller.client
        self._controller = controller
        self._primary_mac_address = (
            controller.mac_address or self._client.controllers[1].mac_address
        )
        self._device_identifier = (
            self._controller.mac_address
            or f"{self._primary_mac_address}-{self._controller.controller_id}"
        )
        self._attr_device_info = DeviceInfo(
            # Use MAC address of Russound device as identifier
            identifiers={(DOMAIN, self._device_identifier)},
            manufacturer="Russound",
            name=controller.controller_type,
            model=controller.controller_type,
            sw_version=controller.firmware_version,
        )
        if isinstance(self._client.connection_handler, RussoundTcpConnectionHandler):
            self._attr_device_info["configuration_url"] = (
                f"http://{self._client.connection_handler.host}"
            )
        if controller.controller_id != 1:
            assert self._client.controllers[1].mac_address
            self._attr_device_info["via_device"] = (
                DOMAIN,
                self._client.controllers[1].mac_address,
            )
        else:
            assert controller.mac_address
            self._attr_device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, controller.mac_address)
            }

    async def _state_update_callback(
        self, _client: RussoundClient, _callback_type: CallbackType
    ) -> None:
        """Call when the device is notified of changes."""
        if _callback_type == CallbackType.CONNECTION:
            self._attr_available = _client.is_connected()
        self._controller = _client.controllers[self._controller.controller_id]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback handlers."""
        await self._client.register_state_update_callbacks(self._state_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        await self._client.unregister_state_update_callbacks(
            self._state_update_callback
        )
