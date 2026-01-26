"""The Google Air Quality integration."""

import asyncio
from collections.abc import Coroutine
import logging
from typing import Any

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.auth import Auth

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFERRER, DOMAIN
from .coordinator import (
    GoogleAirQualityConfigEntry,
    GoogleAirQualityCurrentConditionsCoordinator,
    GoogleAirQualityForecastCoordinator,
    GoogleAirQualityRuntimeData,
    GoogleAirQualitySubEntryRuntimeData,
)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


def _async_cleanup_orphaned_forecast_devices(
    hass: HomeAssistant,
    entry: GoogleAirQualityConfigEntry,
) -> None:
    """Remove forecast devices that are no longer configured."""
    device_registry = dr.async_get(hass)
    wanted_devices: set[str] = set()

    for subentry in entry.subentries.values():
        for hour in subentry.data.get("forecast", []):
            wanted_devices.add(
                f"{entry.entry_id}_{subentry.subentry_id}_forecast_{hour}h"
            )
    registered_devices: dict[str, dr.DeviceEntry] = {}

    for device in device_registry.devices.get_devices_for_config_entry_id(
        entry.entry_id
    ):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            if "_forecast_" in identifier:
                registered_devices[identifier] = device

    orphaned = set(registered_devices) - wanted_devices

    if not orphaned:
        return

    _LOGGER.debug("Removing orphaned forecast devices: %s", orphaned)

    for identifier in orphaned:
        device = registered_devices[identifier]
        device_registry.async_update_device(
            device_id=device.id,
            remove_config_entry_id=entry.entry_id,
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> bool:
    """Set up Google Air Quality from a config entry."""
    session = async_get_clientsession(hass)
    api_key = entry.data[CONF_API_KEY]
    referrer = entry.data.get(CONF_REFERRER)
    auth = Auth(session, api_key, referrer=referrer)
    client = GoogleAirQualityApi(auth)
    _async_cleanup_orphaned_forecast_devices(hass, entry)
    subentries_runtime_data: dict[str, GoogleAirQualitySubEntryRuntimeData] = {}
    for subentry in entry.subentries.values():
        subentry_runtime_data = GoogleAirQualitySubEntryRuntimeData(
            coordinator_current_conditions=GoogleAirQualityCurrentConditionsCoordinator(
                hass,
                entry,
                subentry.subentry_id,
                client,
            ),
            coordinators_forecast={},
        )

        if subentry.data.get("forecast"):
            for hour in subentry.data.get("forecast", []):
                subentry_runtime_data.coordinators_forecast[hour] = (
                    GoogleAirQualityForecastCoordinator(
                        hass,
                        entry,
                        subentry.subentry_id,
                        client,
                        hour,
                    )
                )

        subentries_runtime_data[subentry.subentry_id] = subentry_runtime_data
    tasks: list[Coroutine[Any, Any, None]] = []

    for data in subentries_runtime_data.values():
        tasks.append(
            data.coordinator_current_conditions.async_config_entry_first_refresh()
        )

        tasks.extend(
            coordinator.async_config_entry_first_refresh()
            for coordinator in data.coordinators_forecast.values()
        )

    await asyncio.gather(*tasks)
    entry.runtime_data = GoogleAirQualityRuntimeData(
        api=client,
        subentries_runtime_data=subentries_runtime_data,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: GoogleAirQualityConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
