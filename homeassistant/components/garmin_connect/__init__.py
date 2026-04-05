"""The Garmin Connect integration."""

from __future__ import annotations

import logging

from ha_garmin import GarminAuth, GarminClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CLIENT_ID, CONF_REFRESH_TOKEN, CONF_TOKEN
from .coordinator import CoreCoordinator, GarminConnectCoordinators

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GarminConnectConfigEntry = ConfigEntry[GarminConnectCoordinators]


async def async_setup_entry(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> bool:
    """Set up Garmin Connect from a config entry."""
    is_cn = hass.config.country == "CN"
    auth = GarminAuth(is_cn=is_cn)
    auth.di_token = entry.data[CONF_TOKEN]
    auth.di_refresh_token = entry.data[CONF_REFRESH_TOKEN]
    auth.di_client_id = entry.data[CONF_CLIENT_ID]

    client = GarminClient(auth, is_cn=is_cn)

    coordinators = GarminConnectCoordinators(
        core=CoreCoordinator(hass, entry, client, auth),
    )

    await coordinators.core.async_config_entry_first_refresh()

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
