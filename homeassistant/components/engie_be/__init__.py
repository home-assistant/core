"""The ENGIE Belgium integration."""

import asyncio
from dataclasses import dataclass

from aioengiebelgium import EngieBeClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN
from .coordinator import EngieBePricesCoordinator, EngieBeRelationsCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class EngieBeHouseholdCoordinators:
    """Per-household coordinators."""

    prices: EngieBePricesCoordinator


@dataclass
class EngieBeRuntimeData:
    """Runtime data for the ENGIE Belgium integration."""

    relations: EngieBeRelationsCoordinator
    households: dict[str, EngieBeHouseholdCoordinators]


type EngieBeConfigEntry = ConfigEntry[EngieBeRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> bool:
    """Set up ENGIE Belgium from a config entry."""

    async def _persist_tokens(access_token: str, refresh_token: str) -> None:
        """Persist rotated tokens to the config entry."""
        if (
            entry.data[CONF_ACCESS_TOKEN] == access_token
            and entry.data[CONF_REFRESH_TOKEN] == refresh_token
        ):
            return
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )

    client = EngieBeClient(
        session=async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        on_token_refresh=_persist_tokens,
    )

    relations = EngieBeRelationsCoordinator(hass, entry, client)
    await relations.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)

    @callback
    def _async_create_household(ban: str) -> EngieBeHouseholdCoordinators:
        """Build the coordinators for a business agreement and register its device."""
        household = EngieBeHouseholdCoordinators(
            prices=EngieBePricesCoordinator(
                hass, entry, client, ban, relations.data[ban]
            )
        )
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **household.prices.device_info
        )
        return household

    households = {ban: _async_create_household(ban) for ban in relations.data}
    await asyncio.gather(
        *(household.prices.async_refresh() for household in households.values())
    )

    entry.runtime_data = EngieBeRuntimeData(relations=relations, households=households)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
