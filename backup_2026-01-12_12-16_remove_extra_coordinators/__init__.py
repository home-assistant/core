"""The Garmin Connect integration."""

from __future__ import annotations

import asyncio
import logging

from aiogarmin import GarminAuth, GarminClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_OAUTH1_TOKEN, CONF_OAUTH2_TOKEN, DOMAIN
from .coordinator import (
    ActivityCoordinator,
    BloodPressureCoordinator,
    BodyCoordinator,
    CoreCoordinator,
    GarminConnectCoordinators,
    GearCoordinator,
    GoalsCoordinator,
    MenstrualCoordinator,
    TrainingCoordinator,
)
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GarminConnectConfigEntry = ConfigEntry[GarminConnectCoordinators]


async def async_setup_entry(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> bool:
    """Set up Garmin Connect from a config entry."""
    session = async_get_clientsession(hass)

    # Create auth with stored tokens
    auth = GarminAuth(
        session,
        oauth1_token=entry.data.get(CONF_OAUTH1_TOKEN),
        oauth2_token=entry.data.get(CONF_OAUTH2_TOKEN),
    )

    # Check if we have valid tokens
    if not auth.oauth1_token:
        raise ConfigEntryAuthFailed("No authentication tokens found")

    # Try to refresh tokens if needed
    try:
        if not auth.oauth2_token:
            result = await auth.refresh_tokens()
            # Update stored tokens
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_OAUTH1_TOKEN: result.oauth1_token,
                    CONF_OAUTH2_TOKEN: result.oauth2_token,
                },
            )
    except Exception as err:
        _LOGGER.error("Failed to authenticate: %s", err)
        raise ConfigEntryAuthFailed("Authentication failed") from err

    # Create client
    is_cn = hass.config.country == "CN"
    client = GarminClient(session, auth, is_cn=is_cn)

    # Create all 8 coordinators
    coordinators = GarminConnectCoordinators(
        core=CoreCoordinator(hass, entry, client, auth),
        activity=ActivityCoordinator(hass, entry, client, auth),
        training=TrainingCoordinator(hass, entry, client, auth),
        body=BodyCoordinator(hass, entry, client, auth),
        goals=GoalsCoordinator(hass, entry, client, auth),
        gear=GearCoordinator(hass, entry, client, auth),
        blood_pressure=BloodPressureCoordinator(hass, entry, client, auth),
        menstrual=MenstrualCoordinator(hass, entry, client, auth),
    )

    # Fetch initial data from all coordinators concurrently
    try:
        await asyncio.gather(
            coordinators.core.async_config_entry_first_refresh(),
            coordinators.activity.async_config_entry_first_refresh(),
            coordinators.training.async_config_entry_first_refresh(),
            coordinators.body.async_config_entry_first_refresh(),
            coordinators.goals.async_config_entry_first_refresh(),
            coordinators.gear.async_config_entry_first_refresh(),
            coordinators.blood_pressure.async_config_entry_first_refresh(),
            coordinators.menstrual.async_config_entry_first_refresh(),
        )
    except Exception as err:
        raise ConfigEntryNotReady from err

    # Store coordinators in runtime_data
    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once, not per entry)
    if not hass.services.has_service(DOMAIN, "set_active_gear"):
        await async_setup_services(hass)

    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    return True


async def async_options_update_listener(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> None:
    """Handle options update - reload integration to apply new scan_interval."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Unload services only when last entry is unloaded
    remaining_entries = len(hass.config_entries.async_entries(DOMAIN))
    if unload_ok and remaining_entries == 1:
        await async_unload_services(hass)

    return unload_ok
