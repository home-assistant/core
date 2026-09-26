"""Base entity for the LibreSync integration."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, override

from aiolibresync import (
    ConfirmationTimeout,
    DeviceState,
    LibreSyncClient,
    NotConnectedError,
)

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER


def handle_errors[**P](
    func: Callable[P, Awaitable[None]],
) -> Callable[P, Coroutine[Any, Any, None]]:
    """Turn the library's command failures into translated errors."""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await func(*args, **kwargs)
        except NotConnectedError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_connected"
            ) from err
        except ConfirmationTimeout as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_confirmed"
            ) from err

    return wrapper


class LibreSyncEntity(Entity):
    """An entity fed by the client's pushed state."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: LibreSyncClient, unique_id: str, name: str) -> None:
        """Initialize the entity."""
        self._client = client
        # No model or serial here: setup keeps them on the device as they
        # arrive, and a None here would overwrite them.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            name=name,
        )

    @property
    def snapshot(self) -> DeviceState:
        """Return the client's current state."""
        return self._client.state

    @property
    @override
    def available(self) -> bool:
        """Return whether both control ports are connected.

        This is deliberately not the hub's power state: the hub answers on
        both ports while switched off.
        """
        return self.snapshot.available

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to state pushed by the client."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.subscribe(self._handle_state))

    @callback
    def _handle_state(self, state: DeviceState) -> None:
        """Write the new state."""
        self.async_write_ha_state()
