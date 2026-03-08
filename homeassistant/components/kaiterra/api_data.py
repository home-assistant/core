"""API helpers for the Kaiterra integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ClientConnectorError
from kaiterra_async_client import AQIStandard, KaiterraAPIClient

from .const import AQI_LEVEL, AQI_SCALE

POLLUTANTS = {
    "rpm25c": "PM2.5",
    "rpm10c": "PM10",
    "tvoc": "TVOC",
    "rco2": "CO2",
}


class KaiterraApiError(Exception):
    """Base Kaiterra API error."""


class KaiterraApiAuthError(KaiterraApiError):
    """Raised when the API key is invalid."""


class KaiterraDeviceNotFoundError(KaiterraApiError):
    """Raised when the configured device does not exist."""


class KaiterraApiClient:
    """Wrapper around the Kaiterra async client."""

    def __init__(self, session, api_key: str, aqi_standard: str) -> None:
        """Initialize the API client."""
        self._api = KaiterraAPIClient(
            session,
            api_key=api_key,
            aqi_standard=AQIStandard.from_str(aqi_standard),
        )
        self._scale = AQI_SCALE[aqi_standard]
        self._level = AQI_LEVEL[aqi_standard]

    async def async_get_latest_sensor_readings(
        self, device_id: str
    ) -> dict[str, dict[str, Any]]:
        """Fetch and normalize the latest sensor readings for one device."""
        try:
            async with asyncio.timeout(10):
                data = await self._api.get_latest_sensor_readings(
                    [f"/devices/{device_id}/top"]
                )
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise KaiterraApiAuthError from err
            raise KaiterraApiError(
                f"API request failed with status {err.status}: {err.message}"
            ) from err
        except (ClientConnectorError, TimeoutError, ValueError) as err:
            raise KaiterraApiError(str(err)) from err

        if not data or data[0] is None:
            raise KaiterraDeviceNotFoundError(device_id)

        try:
            return _normalize_device_data(data[0], self._scale, self._level)
        except (IndexError, TypeError, ValueError) as err:
            raise KaiterraApiError(f"Failed to normalize sensor payload: {err}") from err


def _normalize_device_data(
    payload: Mapping[str, Any], scale: list[int], levels: list[str]
) -> dict[str, dict[str, Any]]:
    """Normalize a single Kaiterra device payload."""
    normalized: dict[str, dict[str, Any]] = {}
    overall_aqi: int | None = None
    main_pollutant: str | None = None

    for sensor_name, sensor in payload.items():
        if not isinstance(sensor, Mapping):
            continue

        points = sensor.get("points")
        if not points or not isinstance(points, list):
            continue

        point = points[0]
        if not isinstance(point, Mapping):
            continue

        sensor_data: dict[str, Any] = {"value": point.get("value")}
        if (unit := _normalize_unit(sensor.get("units"))) is not None:
            sensor_data["unit"] = unit

        if "aqi" in point:
            sensor_data["aqi"] = point["aqi"]
            if overall_aqi is None or point["aqi"] > overall_aqi:
                overall_aqi = point["aqi"]
                main_pollutant = POLLUTANTS.get(sensor_name)

        normalized[sensor_name] = sensor_data

    level: str | None = None
    if overall_aqi is not None:
        for index in range(1, len(scale)):
            if overall_aqi <= scale[index]:
                level = levels[index - 1]
                break

    normalized["aqi"] = {"value": overall_aqi}
    normalized["aqi_level"] = {"value": level}
    normalized["aqi_pollutant"] = {"value": main_pollutant}
    return normalized


def _normalize_unit(unit: Any) -> str | None:
    """Normalize unit values returned by the API client."""
    if unit is None:
        return None
    if hasattr(unit, "value"):
        return unit.value
    if isinstance(unit, str):
        return unit
    return str(unit)
