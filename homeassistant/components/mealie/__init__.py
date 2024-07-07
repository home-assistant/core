"""The Mealie integration."""

from __future__ import annotations

from aiomealie import MealieAuthenticationError, MealieClient, MealieConnectionError

from homeassistant.const import CONF_API_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import DOMAIN
from .coordinator import MealieConfigEntry, MealieCoordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: MealieConfigEntry) -> bool:
    """Set up Mealie from a config entry."""
    client = MealieClient(
        entry.data[CONF_HOST],
        token=entry.data[CONF_API_TOKEN],
        session=async_get_clientsession(hass),
    )
    try:
        about = await client.get_about()
    except MealieAuthenticationError as error:
        raise ConfigEntryError("Authentication failed") from error
    except MealieConnectionError as error:
        raise ConfigEntryNotReady(error) from error

    assert entry.unique_id
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        entry_type=DeviceEntryType.SERVICE,
        sw_version=about.version,
    )

    coordinator = MealieCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MealieConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
