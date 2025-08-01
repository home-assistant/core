"""Base entity for Russound RIO integration."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aiorussound import Controller, RussoundClient
from aiorussound.models import CallbackType
from aiorussound.rio import ZoneControlSurface

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
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
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={
                    "function_name": func.__name__,
                    "entity_id": self.entity_id,
                },
            ) from exc

    return decorator


class RussoundBaseEntity(Entity):
    """Russound Base Entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        controller: Controller,
        zone_id: int | None = None,
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
        self._zone_id = zone_id
        if not zone_id:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._device_identifier)},
            )
            return
        zone = controller.zones[zone_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._device_identifier}-{zone_id}")},
            name=zone.name,
            manufacturer="Russound",
            model=controller.controller_type,
            sw_version=controller.firmware_version,
            suggested_area=zone.name,
            via_device=(DOMAIN, self._device_identifier),
        )

    @property
    def _zone(self) -> ZoneControlSurface:
        assert self._zone_id
        return self._controller.zones[self._zone_id]

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
        self._client.unregister_state_update_callbacks(self._state_update_callback)
