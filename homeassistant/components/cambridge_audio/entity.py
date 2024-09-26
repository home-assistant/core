"""Base class for Cambridge Audio entities."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aiostreammagic import StreamMagicClient
from aiostreammagic.models import CallbackType

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, STREAM_MAGIC_EXCEPTIONS


def command[_EntityT: CambridgeAudioEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Awaitable[None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Wrap async calls to raise on request error."""

    @wraps(func)
    async def decorator(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(self, *args, **kwargs)
        except STREAM_MAGIC_EXCEPTIONS as exc:
            raise HomeAssistantError(
                f"Error executing {func.__name__} on entity {self.entity_id},"
            ) from exc

    return decorator


class CambridgeAudioEntity(Entity):
    """Defines a base Cambridge Audio entity."""

    _attr_has_entity_name = True

    def __init__(self, client: StreamMagicClient) -> None:
        """Initialize Cambridge Audio entity."""
        self.client = client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.info.unit_id)},
            name=client.info.name,
            manufacturer="Cambridge Audio",
            model=client.info.model,
            serial_number=client.info.unit_id,
            configuration_url=f"http://{client.host}",
        )

    async def _state_update_callback(
        self, _client: StreamMagicClient, _callback_type: CallbackType
    ) -> None:
        """Call when the device is notified of changes."""
        self._attr_available = _client.is_connected()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback handlers."""
        await self.client.register_state_update_callbacks(self._state_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        await self.client.unregister_state_update_callbacks(self._state_update_callback)
