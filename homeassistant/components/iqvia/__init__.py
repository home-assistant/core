"""Support for IQVIA."""

from __future__ import annotations

import asyncio

from pyiqvia import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_ZIP_CODE,
    DOMAIN,
    TYPE_ALLERGY_FORECAST,
    TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_OUTLOOK,
    TYPE_ASTHMA_FORECAST,
    TYPE_ASTHMA_INDEX,
    TYPE_DISEASE_FORECAST,
    TYPE_DISEASE_INDEX,
)
from .coordinator import IqviaUpdateCoordinator

DEFAULT_ATTRIBUTION = "Data provided by IQVIA™"

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IQVIA as config entry."""
    if not entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_ZIP_CODE]
        )

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(entry.data[CONF_ZIP_CODE], session=websession)

    # We disable the client's request retry abilities here to avoid a lengthy (and
    # blocking) startup:
    client.disable_request_retries()

    coordinators = {}
    init_data_update_tasks = []

    for sensor_type, api_coro in (
        (TYPE_ALLERGY_FORECAST, client.allergens.extended),
        (TYPE_ALLERGY_INDEX, client.allergens.current),
        (TYPE_ALLERGY_OUTLOOK, client.allergens.outlook),
        (TYPE_ASTHMA_FORECAST, client.asthma.extended),
        (TYPE_ASTHMA_INDEX, client.asthma.current),
        (TYPE_DISEASE_FORECAST, client.disease.extended),
        (TYPE_DISEASE_INDEX, client.disease.current),
    ):
        coordinator = coordinators[sensor_type] = IqviaUpdateCoordinator(
            hass,
            client=client,
            config_entry=entry,
            name=f"{entry.data[CONF_ZIP_CODE]} {sensor_type}",
            update_method=api_coro,
        )
        init_data_update_tasks.append(coordinator.async_refresh())

    results = await asyncio.gather(*init_data_update_tasks, return_exceptions=True)
    if all(isinstance(result, Exception) for result in results):
        # The IQVIA API can be selectively flaky, meaning that any number of the setup
        # API calls could fail. We only retry integration setup if *all* of the initial
        # API calls fail:
        raise ConfigEntryNotReady

    # Once we've successfully authenticated, we re-enable client request retries:
    client.enable_request_retries()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OpenUV config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
