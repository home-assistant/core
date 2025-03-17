"""Support for Velbus devices."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from velbusaio.channels import Channel as VelbusChannel

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

# device identifiers for modules
# (DOMAIN, module_address)

# device identifiers for channels that are subdevices of a module
# (DOMAIN, f"{module_address}-{channel_number}")


class VelbusEntity(Entity):
    """Representation of a Velbus entity."""

    _attr_has_entity_name = True
    _attr_should_poll: bool = False

    def __init__(self, channel: VelbusChannel) -> None:
        """Initialize a Velbus entity."""
        self._channel = channel
        self._module_adress = str(channel.get_module_address())
        self._attr_name = channel.get_name()
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self._get_identifier()),
            },
            manufacturer="Velleman",
            model=channel.get_module_type_name(),
            model_id=str(channel.get_module_type()),
            name=channel.get_full_name(),
            sw_version=channel.get_module_sw_version(),
            serial_number=channel.get_module_serial(),
        )
        if self._channel.is_sub_device():
            self._attr_device_info["via_device"] = (
                DOMAIN,
                self._module_adress,
            )
        serial = channel.get_module_serial() or self._module_adress
        self._attr_unique_id = f"{serial}-{channel.get_channel_number()}"

    def _get_identifier(self) -> str:
        """Return the identifier of the entity."""
        if not self._channel.is_sub_device():
            return self._module_adress
        return f"{self._module_adress}-{self._channel.get_channel_number()}"

    async def async_added_to_hass(self) -> None:
        """Add listener for state changes."""
        self._channel.on_status_update(self._on_update)

    async def async_will_remove_from_hass(self) -> None:
        """Remove listener for state changes."""
        self._channel.remove_on_status_update(self._on_update)

    async def _on_update(self) -> None:
        self.async_write_ha_state()


def api_call[_T: VelbusEntity, **_P](
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
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
