"""The Eve Online integration."""

from __future__ import annotations

import asyncio

from eveonline import EveOnlineClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AsyncConfigEntryAuth
from .const import CONF_CHARACTER_ID, CONF_CHARACTER_NAME
from .coordinator import (
    EveOnlineConfigEntry,
    EveOnlineCoordinator,
    EveOnlineIndustryCoordinator,
    EveOnlineMarketCoordinator,
    EveOnlineRuntimeData,
    EveOnlineSkillsCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EveOnlineConfigEntry) -> bool:
    """Set up Eve Online from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session)
    client = EveOnlineClient(auth=auth)

    character_id: int = entry.data[CONF_CHARACTER_ID]
    character_name: str = entry.data[CONF_CHARACTER_NAME]

    coordinator = EveOnlineCoordinator(
        hass, entry, client, character_id, character_name
    )
    industry_coordinator = EveOnlineIndustryCoordinator(
        hass, entry, client, character_id, character_name
    )
    market_coordinator = EveOnlineMarketCoordinator(
        hass, entry, client, character_id, character_name
    )
    skills_coordinator = EveOnlineSkillsCoordinator(
        hass, entry, client, character_id, character_name
    )

    await asyncio.gather(
        coordinator.async_config_entry_first_refresh(),
        industry_coordinator.async_config_entry_first_refresh(),
        market_coordinator.async_config_entry_first_refresh(),
        skills_coordinator.async_config_entry_first_refresh(),
    )

    entry.runtime_data = EveOnlineRuntimeData(
        coordinator=coordinator,
        industry_coordinator=industry_coordinator,
        market_coordinator=market_coordinator,
        skills_coordinator=skills_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EveOnlineConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
