"""Support for LG webOS TV switch."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, override

from aiowebostv import WebOsClient, WebOsTvCommandError, WebOsTvState

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebOsTvConfigEntry
from .const import DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG webOS TV switch platform."""
    client = entry.runtime_data

    async_add_entities([LgWebOSScreenSwitchEntity(entry, client)])


def cmd[_R, **_P](
    func: Callable[Concatenate[LgWebOSScreenSwitchEntity, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[LgWebOSScreenSwitchEntity, _P], Coroutine[Any, Any, _R]]:
    """Catch command exceptions."""

    @wraps(func)
    async def cmd_wrapper(
        self: LgWebOSScreenSwitchEntity, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        """Wrap all command methods."""
        try:
            return await func(self, *args, **kwargs)
        except WebOsTvCommandError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={
                    "func": func.__name__,
                    "name": self._entry.title,
                    "error": str(exc),
                },
            ) from exc

    return cmd_wrapper


class LgWebOSScreenSwitchEntity(SwitchEntity):
    """Representation of a LG webOS TV Screen Switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "screen"

    def __init__(self, entry: WebOsTvConfigEntry, client: WebOsClient) -> None:
        """Initialize the screen switch entity."""
        self._entry = entry
        self._client = client
        self._attr_unique_id = f"{entry.unique_id}_screen"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Connect to client signals."""
        await super().async_added_to_hass()
        await self._client.register_state_update_callback(
            self.async_handle_state_update
        )
        self._update_states()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister state update callback."""
        self._client.unregister_state_update_callback(self.async_handle_state_update)

    async def async_handle_state_update(self, tv_state: WebOsTvState) -> None:
        """Update state from WebOsClient."""
        self._update_states()
        self.async_write_ha_state()

    def _update_states(self) -> None:
        """Update entity attributes."""
        self._attr_available = self._client.tv_state.is_on
        self._attr_is_on = self._client.tv_state.is_screen_on

    @cmd
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the screen on."""
        await self._client.request("com.webos.service.tvpower/power/turnOnScreen")

    @cmd
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen off."""
        await self._client.request("com.webos.service.tvpower/power/turnOffScreen")
