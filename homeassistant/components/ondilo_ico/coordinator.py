"""Define an object to coordinate fetching Ondilo ICO data."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from ondilo import OndiloError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import DOMAIN
from .api import OndiloClient

_LOGGER = logging.getLogger(__name__)

TIME_TO_NEXT_UPDATE = timedelta(hours=1, minutes=5)
UPDATE_LOCK = asyncio.Lock()


@dataclass
class OndiloIcoPoolData:
    """Store the pools the data."""

    ico: dict[str, Any]
    pool: dict[str, Any]
    measures_coordinator: OndiloIcoMeasuresCoordinator = field(init=False)


@dataclass
class OndiloIcoMeasurementData:
    """Store the measurement data for one pool."""

    sensors: dict[str, Any]


class OndiloIcoPoolsCoordinator(DataUpdateCoordinator[dict[str, OndiloIcoPoolData]]):
    """Fetch Ondilo ICO pools data from API."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: OndiloClient
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_pools",
            update_interval=timedelta(minutes=20),
        )
        self.api = api
        self.config_entry = config_entry
        self._device_registry = dr.async_get(self.hass)

    async def _async_update_data(self) -> dict[str, OndiloIcoPoolData]:
        """Fetch pools data from API endpoint and update devices."""
        known_pools: set[str] = set(self.data) if self.data else set()
        try:
            async with UPDATE_LOCK:
                data = await self.hass.async_add_executor_job(self._update_data)
        except OndiloError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        current_pools = set(data)

        new_pools = current_pools - known_pools
        for pool_id in new_pools:
            pool_data = data[pool_id]
            pool_data.measures_coordinator = OndiloIcoMeasuresCoordinator(
                self.hass, self.config_entry, self.api, pool_id
            )
            self._device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, pool_data.ico["serial_number"])},
                manufacturer="Ondilo",
                model="ICO",
                name=pool_data.pool["name"],
                sw_version=pool_data.ico["sw_version"],
            )

        removed_pools = known_pools - current_pools
        for pool_id in removed_pools:
            pool_data = self.data.pop(pool_id)
            await pool_data.measures_coordinator.async_shutdown()
            device_entry = self._device_registry.async_get_device(
                identifiers={(DOMAIN, pool_data.ico["serial_number"])}
            )
            if device_entry:
                self._device_registry.async_update_device(
                    device_id=device_entry.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

        for pool_id in current_pools:
            pool_data = data[pool_id]
            measures_coordinator = pool_data.measures_coordinator
            measures_coordinator.set_next_refresh(pool_data)
            if not measures_coordinator.data:
                await measures_coordinator.async_refresh()

        return data

    def _update_data(self) -> dict[str, OndiloIcoPoolData]:
        """Fetch pools data from API endpoint."""
        res = {}
        pools = self.api.get_pools()
        _LOGGER.debug("Pools: %s", pools)
        error: OndiloError | None = None
        for pool in pools:
            pool_id = pool["id"]
            if (data := self.data) and pool_id in data:
                pool_data = res[pool_id] = data[pool_id]
                pool_data.pool = pool
                # Skip requesting new ICO data for known pools
                # to avoid unnecessary API calls.
                continue
            try:
                ico = self.api.get_ICO_details(pool_id)
            except OndiloError as err:
                error = err
                _LOGGER.debug("Error communicating with API for %s: %s", pool_id, err)
                continue

            if not ico:
                _LOGGER.debug("The pool id %s does not have any ICO attached", pool_id)
                continue

            res[pool_id] = OndiloIcoPoolData(ico=ico, pool=pool)
        if not res:
            if error:
                raise UpdateFailed(f"Error communicating with API: {error}") from error
        return res


class OndiloIcoMeasuresCoordinator(DataUpdateCoordinator[OndiloIcoMeasurementData]):
    """Fetch Ondilo ICO measurement data for one pool from API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: OndiloClient,
        pool_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            config_entry=config_entry,
            logger=_LOGGER,
            name=f"{DOMAIN}_measures_{pool_id}",
        )
        self.api = api
        self._next_refresh: datetime | None = None
        self._pool_id = pool_id

    async def _async_update_data(self) -> OndiloIcoMeasurementData:
        """Fetch measurement data from API endpoint."""
        async with UPDATE_LOCK:
            data = await self.hass.async_add_executor_job(self._update_data)
        if next_refresh := self._next_refresh:
            now = dt_util.utcnow()
            # If we've missed the next refresh, schedule a refresh in one hour.
            if next_refresh <= now:
                next_refresh = now + timedelta(hours=1)
            self.update_interval = next_refresh - now

        return data

    def _update_data(self) -> OndiloIcoMeasurementData:
        """Fetch measurement data from API endpoint."""
        try:
            sensors = self.api.get_last_pool_measures(self._pool_id)
        except OndiloError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return OndiloIcoMeasurementData(
            sensors={sensor["data_type"]: sensor["value"] for sensor in sensors},
        )

    def set_next_refresh(self, pool_data: OndiloIcoPoolData) -> None:
        """Set next refresh of this coordinator."""
        last_update = datetime.fromisoformat(pool_data.pool["updated_at"])
        self._next_refresh = last_update + TIME_TO_NEXT_UPDATE
