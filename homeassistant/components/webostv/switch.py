"""Support for LG webOS TV switch."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, cast, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WEBOSTV_EXCEPTIONS
from .coordinator import WebOsTvConfigEntry, WebOsTvDataUpdateCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG webOS TV switch platform."""
    async_add_entities([LgWebOSScreenSwitchEntity(entry)])


def cmd[_R, **_P](
    func: Callable[Concatenate[LgWebOSScreenSwitchEntity, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[LgWebOSScreenSwitchEntity, _P], Coroutine[Any, Any, _R]]:
    """Catch command exceptions."""

    @wraps(func)
    async def cmd_wrapper(
        self: LgWebOSScreenSwitchEntity, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        """Wrap all command methods."""
        if not self.coordinator.client.tv_state.is_on:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_off",
                translation_placeholders={
                    "func": func.__name__,
                    "name": str(self._entry.title),
                },
            )
        try:
            return await func(self, *args, **kwargs)
        except WEBOSTV_EXCEPTIONS as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={
                    "func": func.__name__,
                    "name": str(self._entry.title),
                    "error": str(exc),
                },
            ) from exc

    return cmd_wrapper


class LgWebOSScreenSwitchEntity(
    CoordinatorEntity[WebOsTvDataUpdateCoordinator], SwitchEntity
):
    """Representation of a LG webOS TV Screen Switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "screen"

    def __init__(self, entry: WebOsTvConfigEntry) -> None:
        """Initialize the screen switch entity."""
        super().__init__(entry.runtime_data)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_screen"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, entry.unique_id))},
            manufacturer="LG",
            name=entry.title,
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if screen is on.

        The library reports the screen as off whenever the TV is off, so this
        stays accurate while the TV is unreachable but the entity is available.
        """
        return self.coordinator.client.tv_state.is_screen_on

    @cmd
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the screen on."""
        await self.coordinator.client.request(
            "com.webos.service.tvpower/power/turnOnScreen"
        )

    @cmd
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen off."""
        await self.coordinator.client.request(
            "com.webos.service.tvpower/power/turnOffScreen"
        )
