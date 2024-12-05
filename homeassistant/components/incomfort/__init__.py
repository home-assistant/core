"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""

from __future__ import annotations

from aiohttp import ClientResponseError
from incomfortclient import IncomfortError, InvalidHeaterList

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .coordinator import InComfortDataCoordinator, async_connect_gateway
from .errors import InConfortTimeout, InConfortUnknownError, NoHeaters, NotFound

PLATFORMS = (
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.CLIMATE,
)

INTEGRATION_TITLE = "Intergas InComfort/Intouch Lan2RF gateway"

type InComfortConfigEntry = ConfigEntry[InComfortDataCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    try:
        data = await async_connect_gateway(hass, dict(entry.data))
        for heater in data.heaters:
            await heater.update()
    except InvalidHeaterList as exc:
        raise NoHeaters from exc
    except IncomfortError as exc:
        if isinstance(exc.message, ClientResponseError):
            if exc.message.status == 401:
                raise ConfigEntryAuthFailed("Incorrect credentials") from exc
            if exc.message.status == 404:
                raise NotFound from exc
        raise InConfortUnknownError from exc
    except TimeoutError as exc:
        raise InConfortTimeout from exc

    coordinator = InComfortDataCoordinator(hass, data)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
