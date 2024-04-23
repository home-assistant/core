"""The radiotherm component."""

from __future__ import annotations

from collections.abc import Coroutine
from typing import Any, TypeVar
from urllib.error import URLError

from radiotherm.validate import RadiothermTstatError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import RadioThermUpdateCoordinator
from .data import async_get_init_data
from .util import async_set_time

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH]

_T = TypeVar("_T")


async def _async_call_or_raise_not_ready(
    coro: Coroutine[Any, Any, _T], host: str
) -> _T:
    """Call a coro or raise ConfigEntryNotReady."""
    try:
        return await coro
    except RadiothermTstatError as ex:
        msg = f"{host} was busy (invalid value returned): {ex}"
        raise ConfigEntryNotReady(msg) from ex
    except TimeoutError as ex:
        msg = f"{host} timed out waiting for a response: {ex}"
        raise ConfigEntryNotReady(msg) from ex
    except (OSError, URLError) as ex:
        msg = f"{host} connection error: {ex}"
        raise ConfigEntryNotReady(msg) from ex


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Radio Thermostat from a config entry."""
    host = entry.data[CONF_HOST]
    init_coro = async_get_init_data(hass, host)
    init_data = await _async_call_or_raise_not_ready(init_coro, host)
    coordinator = RadioThermUpdateCoordinator(hass, init_data)
    await coordinator.async_config_entry_first_refresh()

    # Only set the time if the thermostat is
    # not in hold mode since setting the time
    # clears the hold for some strange design
    # choice
    if not coordinator.data.tstat["hold"]:
        time_coro = async_set_time(hass, init_data.tstat)
        await _async_call_or_raise_not_ready(time_coro, host)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
