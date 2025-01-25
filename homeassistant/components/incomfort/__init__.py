"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""

from __future__ import annotations

from aiohttp import ClientResponseError
from incomfortclient import InvalidGateway, InvalidHeaterList

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import InComfortDataCoordinator, async_connect_gateway
from .errors import InComfortTimeout, InComfortUnknownError, NoHeaters, NotFound

PLATFORMS = (
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.CLIMATE,
)

INTEGRATION_TITLE = "Intergas InComfort/Intouch Lan2RF gateway"

type InComfortConfigEntry = ConfigEntry[InComfortDataCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: InComfortConfigEntry) -> bool:
    """Set up a config entry."""
    try:
        data = await async_connect_gateway(hass, dict(entry.data))
        for heater in data.heaters:
            await heater.update()
    except InvalidHeaterList as exc:
        raise NoHeaters from exc
    except InvalidGateway as exc:
        raise ConfigEntryAuthFailed("Incorrect credentials") from exc
    except ClientResponseError as exc:
        if exc.status == 404:
            raise NotFound from exc
        raise InComfortUnknownError from exc
    except TimeoutError as exc:
        raise InComfortTimeout from exc

    # Register discovered gateway device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
        if entry.unique_id is not None
        else set(),
        manufacturer="Intergas",
        name="RFGateway",
    )
    coordinator = InComfortDataCoordinator(hass, data, entry.entry_id)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InComfortConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
