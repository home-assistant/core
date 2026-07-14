"""Data update coordinators for the GridX integration."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypedDict, override

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


# Ratio values (0..1) must be averaged across systems, not summed.
_RATE_KEYS = frozenset(
    {
        "directConsumptionRate",
        "selfConsumptionRate",
        "selfSufficiencyRate",
        "stateOfCharge",
    }
)


def _merge_values(key: str, values: list[Any]) -> Any:
    """Merge one key's values from multiple systems."""
    first_non_null = next((value for value in values if value is not None), None)
    if not isinstance(first_non_null, int | float):
        return first_non_null
    numeric = [value for value in values if isinstance(value, int | float)]
    if key in _RATE_KEYS:
        return sum(numeric) / len(numeric)
    return sum(numeric)


def _aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-system results into a single mapping.

    Numeric values are summed (rates averaged), nested mappings are
    aggregated recursively, lists are concatenated and other values are
    taken from the first system providing them.
    """
    if len(results) == 1:
        return results[0]
    keys: dict[str, None] = {}
    for result in results:
        keys.update(dict.fromkeys(result))
    merged: dict[str, Any] = {}
    for key in keys:
        values = [result[key] for result in results if key in result]
        if nested := [value for value in values if isinstance(value, dict)]:
            merged[key] = _aggregate_results(nested)
        elif any(isinstance(value, list) for value in values):
            merged[key] = [
                item for value in values if isinstance(value, list) for item in value
            ]
        else:
            merged[key] = _merge_values(key, values)
    return merged


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
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except httpx.HTTPError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except (RuntimeError, TypeError, ValueError) as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    if not results:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="no_data",
        )
    return _aggregate_results(results)


async def _fetch_historical(connector: GridxConnector) -> GridxHistoricalData:
    """Fetch today's historical totals."""
    midnight = dt_util.start_of_local_day()
    tomorrow = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))

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
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except httpx.HTTPError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except (RuntimeError, TypeError, ValueError) as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    if not results:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="no_data",
        )

    totals = [
        result["total"] for result in results if isinstance(result.get("total"), dict)
    ]
    total = _aggregate_results(totals) if totals else {}
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

    @override
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

    @override
    async def _async_update_data(self) -> GridxHistoricalData:
        """Fetch historical totals."""
        return await _fetch_historical(self._connector)
