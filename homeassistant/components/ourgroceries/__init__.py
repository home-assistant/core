"""The OurGroceries integration."""

from __future__ import annotations

from aiohttp import ClientError
from ourgroceries import OurGroceries
from ourgroceries.exceptions import InvalidLoginException

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import OurGroceriesConfigEntry, OurGroceriesDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.TODO]


async def async_setup_entry(
    hass: HomeAssistant, entry: OurGroceriesConfigEntry
) -> bool:
    """Set up OurGroceries from a config entry."""
    data = entry.data
    og = OurGroceries(data[CONF_USERNAME], data[CONF_PASSWORD])
    try:
        await og.login()
    except (TimeoutError, ClientError) as error:
        raise ConfigEntryNotReady from error
    except InvalidLoginException:
        return False

    coordinator = OurGroceriesDataUpdateCoordinator(hass, entry, og)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OurGroceriesConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
