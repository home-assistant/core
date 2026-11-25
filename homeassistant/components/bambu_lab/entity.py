"""Base entity for the Bambu Lab integration."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, override

from aiobambulab import BambuLabClient, BambuLabError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


def command[_EntityT: BambuLabEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Awaitable[None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Raise a Home Assistant error when a command cannot be sent."""

    @wraps(func)
    async def wrapper(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except BambuLabError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
            ) from err

    return wrapper


class BambuLabEntity(Entity):
    """Base class for the entities of a Bambu Lab printer."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: BambuLabClient) -> None:
        """Initialize the entity."""
        self._client = client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.serial)},
            manufacturer="Bambu Lab",
            model=client.info.model_name,
            serial_number=client.serial,
            sw_version=client.info.firmware_version,
            hw_version=client.info.hardware_version,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the printer once the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.add_listener(self.async_write_ha_state))

    @override
    @property
    def available(self) -> bool:
        """Return whether the printer is available."""
        return super().available and self._client.available
