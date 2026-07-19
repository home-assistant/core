"""Support for LG webOS TV switches."""

from collections.abc import Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate, cast, override

from aiowebostv import WebOsClient, WebOsTvState

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, WEBOSTV_EXCEPTIONS
from .helpers import WebOsTvConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG webOS TV switches."""
    async_add_entities([LgWebOSScreenSwitchEntity(entry)])


def cmd[_R, **_P](
    func: Callable[
        Concatenate["LgWebOSScreenSwitchEntity", _P], Coroutine[Any, Any, _R]
    ],
) -> Callable[Concatenate["LgWebOSScreenSwitchEntity", _P], Coroutine[Any, Any, _R]]:
    """Catch command exceptions."""

    @wraps(func)
    async def cmd_wrapper(
        self: "LgWebOSScreenSwitchEntity", *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        """Wrap all command methods."""
        try:
            return await func(self, *args, **kwargs)
        except WEBOSTV_EXCEPTIONS as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={
                    "name": str(self._entry.title),
                    "func": func.__name__,
                    "error": str(error),
                },
            ) from error

    return cmd_wrapper


class LgWebOSScreenSwitchEntity(SwitchEntity):
    """Representation of an LG webOS TV screen switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "screen"
    _attr_name = "Screen"

    def __init__(self, entry: WebOsTvConfigEntry) -> None:
        """Initialize the screen switch entity."""
        self._entry = entry
        self._client: WebOsClient = entry.runtime_data
        self._attr_unique_id = f"{entry.unique_id}_screen"
        self._update_states()

    @override
    async def async_added_to_hass(self) -> None:
        """Connect and subscribe to state updates."""
        await super().async_added_to_hass()
        await self._client.register_state_update_callback(
            self.async_handle_state_update
        )
        self._update_states()

    async def async_handle_state_update(self, tv_state: WebOsTvState) -> None:
        """Update state from WebOsClient."""
        self._update_states()
        self.async_write_ha_state()

    def _update_states(self) -> None:
        """Update entity states."""
        tv_state = self._client.tv_state
        self._attr_is_on = tv_state.is_screen_on
        self._attr_available = tv_state.is_on
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, self._entry.unique_id))},
            manufacturer="LG",
            name=self._entry.title,
        )

    @cmd
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the screen on."""
        await self._client.request("com.webos.service.tvpower/power/turnOnScreen")

    @cmd
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen off."""
        await self._client.request("com.webos.service.tvpower/power/turnOffScreen")
