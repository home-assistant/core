"""The Monarch Money integration."""

from __future__ import annotations

from aiohttp import ClientResponseError
from gql.transport.exceptions import TransportServerError
from monarchmoney import MonarchMoney
from monarchmoney.monarchmoney import LoginFailedException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .coordinator import MonarchMoneyDataUpdateCoordinator

type MonarchMoneyConfigEntry = ConfigEntry[MonarchMoneyDataUpdateCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: MonarchMoneyConfigEntry
) -> bool:
    """Set up Monarch Money from a config entry."""
    monarch_client = MonarchMoney(token=entry.data.get(CONF_TOKEN))

    try:
        await monarch_client.get_subscription_details()
    except (TransportServerError, LoginFailedException, ClientResponseError) as err:
        raise ConfigEntryError("Authentication failed") from err

    mm_coordinator = MonarchMoneyDataUpdateCoordinator(hass, monarch_client)
    await mm_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = mm_coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MonarchMoneyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
