"""Support for Roku."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, TypeVar

from rokuecp import RokuConnectionError, RokuError
from typing_extensions import Concatenate, ParamSpec

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import RokuDataUpdateCoordinator
from .entity import RokuEntity

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SELECT,
    Platform.SENSOR,
]
_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T", bound="RokuEntity")
_P = ParamSpec("_P")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roku from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if not (coordinator := hass.data[DOMAIN].get(entry.entry_id)):
        coordinator = RokuDataUpdateCoordinator(hass, host=entry.data[CONF_HOST])
        hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def roku_exception_handler(
    func: Callable[Concatenate[_T, _P], Awaitable[None]]  # type: ignore[misc]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:  # type: ignore[misc]
    """Decorate Roku calls to handle Roku exceptions."""

    @wraps(func)
    async def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except RokuConnectionError as error:
            if self.available:
                _LOGGER.error("Error communicating with API: %s", error)
        except RokuError as error:
            if self.available:
                _LOGGER.error("Invalid response from API: %s", error)

    return wrapper
