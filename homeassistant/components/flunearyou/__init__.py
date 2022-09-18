"""The flunearyou component."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
from typing import Any

from pyflunearyou import Client
from pyflunearyou.errors import FluNearYouError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CATEGORY_CDC_REPORT, CATEGORY_USER_REPORT, DOMAIN, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=30)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flu Near You as config entry."""
    async_create_issue(
        hass,
        DOMAIN,
        "integration_removal",
        is_fixable=True,
        severity=IssueSeverity.ERROR,
        translation_key="integration_removal",
    )

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(session=websession)

    latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)

    async def async_update(api_category: str) -> dict[str, Any]:
        """Get updated date from the API based on category."""
        try:
            if api_category == CATEGORY_CDC_REPORT:
                data = await client.cdc_reports.status_by_coordinates(
                    latitude, longitude
                )
            else:
                data = await client.user_reports.status_by_coordinates(
                    latitude, longitude
                )
        except FluNearYouError as err:
            raise UpdateFailed(err) from err

        return data

    coordinators = {}
    data_init_tasks = []

    for api_category in (CATEGORY_CDC_REPORT, CATEGORY_USER_REPORT):
        coordinator = coordinators[api_category] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{api_category} ({latitude}, {longitude})",
            update_interval=DEFAULT_UPDATE_INTERVAL,
            update_method=partial(async_update, api_category),
        )
        data_init_tasks.append(coordinator.async_config_entry_first_refresh())

    await asyncio.gather(*data_init_tasks)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Flu Near You config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
