"""Define an object to coordinate fetching Ondilo ICO data."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from ondilo import OndiloError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import DOMAIN
from .api import OndiloClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class OndiloIcoData:
    """Class for storing the data."""

    ico: dict[str, Any]
    pool: dict[str, Any]
    sensors: dict[str, Any]


class OndiloIcoCoordinator(DataUpdateCoordinator[dict[str, OndiloIcoData]]):
    """Class to manage fetching Ondilo ICO data from API."""

    def __init__(self, hass: HomeAssistant, api: OndiloClient) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=20),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, OndiloIcoData]:
        """Fetch data from API endpoint."""
        try:
            return await self.hass.async_add_executor_job(self._update_data)
        except OndiloError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _update_data(self) -> dict[str, OndiloIcoData]:
        """Fetch data from API endpoint."""
        res = {}
        pools = self.api.get_pools()
        _LOGGER.debug("Pools: %s", pools)
        error: OndiloError | None = None
        for pool in pools:
            pool_id = pool["id"]
            try:
                ico = self.api.get_ICO_details(pool_id)
                if not ico:
                    _LOGGER.debug(
                        "The pool id %s does not have any ICO attached", pool_id
                    )
                    continue
                sensors = self.api.get_last_pool_measures(pool_id)
            except OndiloError as err:
                error = err
                _LOGGER.debug("Error communicating with API for %s: %s", pool_id, err)
                continue
            res[pool_id] = OndiloIcoData(
                ico=ico,
                pool=pool,
                sensors={sensor["data_type"]: sensor["value"] for sensor in sensors},
            )
        if not res:
            if error:
                raise UpdateFailed(f"Error communicating with API: {error}") from error
            raise UpdateFailed("No data available")
        return res
