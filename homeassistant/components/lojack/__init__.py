"""The LoJack integration for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass, field

from lojack_api import ApiError, AuthenticationError, LoJackClient, Vehicle

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import LoJackCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


@dataclass
class LoJackData:
    """Runtime data for a LoJack config entry."""

    client: LoJackClient
    coordinators: list[LoJackCoordinator] = field(default_factory=list)


type LoJackConfigEntry = ConfigEntry[LoJackData]


async def async_setup_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Set up LoJack from a config entry."""
    session = async_get_clientsession(hass)

    try:
        client = await LoJackClient.create(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            session=session,
        )
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except ApiError as err:
        raise ConfigEntryNotReady(f"API error during setup: {err}") from err

    try:
        vehicles = await client.list_devices()
    except AuthenticationError as err:
        await client.close()
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except ApiError as err:
        await client.close()
        raise ConfigEntryNotReady(f"API error during setup: {err}") from err

    data = LoJackData(client=client)
    entry.runtime_data = data

    try:
        for vehicle in vehicles or []:
            if isinstance(vehicle, Vehicle):
                coordinator = LoJackCoordinator(hass, client, entry, vehicle)
                await coordinator.async_config_entry_first_refresh()
                data.coordinators.append(coordinator)
    except Exception:
        await client.close()
        raise

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LoJackConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok
