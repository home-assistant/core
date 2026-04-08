"""Data update coordinators for the GridX integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypedDict

import httpx

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import GridxConnector
from .const import DOMAIN, HIST_UPDATE_INTERVAL, LIVE_UPDATE_INTERVAL, LOGGER

if TYPE_CHECKING:
    from .types import GridxConfigEntry


class GridxHistoricalData(TypedDict):
    """Data returned by the historical coordinator."""

    total: dict[str, Any]
    last_reset: str  # ISO-8601 local midnight, e.g. "2024-01-01T00:00:00+01:00"


async def _fetch_live(connector: GridxConnector) -> dict[str, Any]:
    """Fetch live data."""
    try:
        results = await connector.retrieve_live_data()
    except PermissionError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except httpx.HTTPStatusError as err:
        status = err.response.status_code if err.response else None
        if status in (401, 403):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        raise UpdateFailed(f"Error fetching GridX live data: {err}") from err
    except httpx.HTTPError as err:
        raise UpdateFailed(f"Error fetching GridX live data: {err}") from err
    except (RuntimeError, TypeError, ValueError) as err:
        raise UpdateFailed(f"Error fetching GridX live data: {err}") from err

    if not results:
        raise UpdateFailed("GridX returned no live data")
    return results[0]


async def _fetch_historical(connector: GridxConnector) -> GridxHistoricalData:
    """Fetch today's historical totals."""
    midnight = dt_util.start_of_local_day()
    tomorrow = midnight + timedelta(days=1)

    try:
        results = await connector.retrieve_historical_data(
            start=midnight.isoformat(),
            end=tomorrow.isoformat(),
            resolution="1d",
        )
    except PermissionError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except httpx.HTTPStatusError as err:
        status = err.response.status_code if err.response else None
        if status in (401, 403):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        raise UpdateFailed(f"Error fetching GridX historical data: {err}") from err
    except httpx.HTTPError as err:
        raise UpdateFailed(f"Error fetching GridX historical data: {err}") from err
    except (RuntimeError, TypeError, ValueError) as err:
        raise UpdateFailed(f"Error fetching GridX historical data: {err}") from err

    if not results:
        raise UpdateFailed("GridX returned no historical data")

    total: dict[str, Any] = {}
    for result in results:
        result_total = result.get("total", {})
        if not isinstance(result_total, dict):
            continue
        for key, value in result_total.items():
            current = total.get(key)
            if isinstance(value, int | float) and isinstance(current, int | float):
                total[key] = current + value
            elif key not in total:
                total[key] = value
    return GridxHistoricalData(total=total, last_reset=midnight.isoformat())


class GridxLiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for GridX live (instantaneous) data."""

    config_entry: GridxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GridxConfigEntry,
        connector: GridxConnector,
    ) -> None:
        """Initialise the live coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{entry.title} live",
            update_interval=LIVE_UPDATE_INTERVAL,
        )
        self._connector = connector

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch live data."""
        return await _fetch_live(self._connector)


class GridxHistoricalCoordinator(DataUpdateCoordinator[GridxHistoricalData]):
    """Coordinator for GridX historical (daily totals) data."""

    config_entry: GridxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GridxConfigEntry,
        connector: GridxConnector,
    ) -> None:
        """Initialise the historical coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{entry.title} historical",
            update_interval=HIST_UPDATE_INTERVAL,
        )
        self._connector = connector

    async def _async_update_data(self) -> GridxHistoricalData:
        """Fetch historical totals."""
        return await _fetch_historical(self._connector)
