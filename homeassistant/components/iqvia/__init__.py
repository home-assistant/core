"""Support for IQVIA."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import partial
from typing import Any

from pyiqvia import Client
from pyiqvia.errors import IQVIAError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_ZIP_CODE,
    DOMAIN,
    LOGGER,
    TYPE_ALLERGY_FORECAST,
    TYPE_ALLERGY_INDEX,
    TYPE_ALLERGY_OUTLOOK,
    TYPE_ASTHMA_FORECAST,
    TYPE_ASTHMA_INDEX,
    TYPE_DISEASE_FORECAST,
    TYPE_DISEASE_INDEX,
)

DEFAULT_ATTRIBUTION = "Data provided by IQVIA™"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

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

    async def async_get_data_from_api(
        api_coro: Callable[[], Coroutine[Any, Any, dict[str, Any]]],
    ) -> dict[str, Any]:
        """Get data from a particular API coroutine."""
        try:
            return await api_coro()
        except IQVIAError as err:
            raise UpdateFailed from err

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
        coordinator = coordinators[sensor_type] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{entry.data[CONF_ZIP_CODE]} {sensor_type}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            update_method=partial(async_get_data_from_api, api_coro),
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


class IQVIAEntity(CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]]):
    """Define a base IQVIA entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{entry.data[CONF_ZIP_CODE]}_{description.key}"
        self._entry = entry
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.last_update_success:
            return

        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if self.entity_description.key == TYPE_ALLERGY_FORECAST:
            self.async_on_remove(
                self.hass.data[DOMAIN][self._entry.entry_id][
                    TYPE_ALLERGY_OUTLOOK
                ].async_add_listener(self._handle_coordinator_update)
            )

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError
