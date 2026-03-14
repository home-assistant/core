"""Data helpers for Kaiterra devices."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ClientConnectorError
from kaiterra_async_client import AQIStandard, KaiterraAPIClient, Units

from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID, CONF_DEVICES, CONF_TYPE
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    AQI_LEVEL,
    AQI_SCALE,
    CONF_AQI_STANDARD,
    CONF_PREFERRED_UNITS,
    DISPATCHER_KAITERRA,
)

_LOGGER = logging.getLogger(__name__)

POLLUTANTS = {
    "rpm25c": "PM2.5",
    "rpm10c": "PM10",
    "rtvoc": "TVOC",
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

    async def async_validate_device(self, device_type: str, device_id: str) -> None:
        """Validate that a device can be read with the provided API key."""
        try:
            async with asyncio.timeout(10):
                data = await self._api.get_latest_sensor_readings(
                    [_build_device_path(device_type, device_id)]
                )
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise KaiterraApiAuthError("Invalid Kaiterra API key") from err
            raise KaiterraApiError(str(err) or "Could not connect to Kaiterra") from err
        except (ClientConnectorError, TimeoutError, ValueError) as err:
            raise KaiterraApiError(str(err) or "Could not connect to Kaiterra") from err

        if not data or data[0] is None:
            raise KaiterraDeviceNotFoundError(f"Device {device_id} was not found")


class KaiterraApiData:
    """Fetch and normalize data for all configured Kaiterra devices."""

    def __init__(self, hass, config: Mapping[str, Any], session) -> None:
        """Initialize the API data object."""
        api_key = config[CONF_API_KEY]
        aqi_standard = config[CONF_AQI_STANDARD]
        devices = config[CONF_DEVICES]
        units = config[CONF_PREFERRED_UNITS]

        self._hass = hass
        self._api = KaiterraAPIClient(
            session,
            api_key=api_key,
            aqi_standard=AQIStandard.from_str(aqi_standard),
            preferred_units=[Units.from_str(unit) for unit in units],
        )
        self._devices_ids = [device[CONF_DEVICE_ID] for device in devices]
        self._devices = [
            _build_device_path(device[CONF_TYPE], device[CONF_DEVICE_ID])
            for device in devices
        ]
        self._scale = AQI_SCALE[aqi_standard]
        self._level = AQI_LEVEL[aqi_standard]
        self.data: dict[str, dict[str, dict[str, Any]]] = {}

    async def async_update(self) -> None:
        """Fetch the latest readings for all configured devices."""
        if not self._devices:
            self.data = {}
            async_dispatcher_send(self._hass, DISPATCHER_KAITERRA)
            return

        try:
            async with asyncio.timeout(10):
                data = await self._api.get_latest_sensor_readings(self._devices)
        except (ClientResponseError, ClientConnectorError, TimeoutError) as err:
            _LOGGER.debug("Couldn't fetch data from Kaiterra API: %s", err)
            self.data = {}
            async_dispatcher_send(self._hass, DISPATCHER_KAITERRA)
            return

        self.data = {}
        for index, device in enumerate(data):
            device_id = self._devices_ids[index]
            if not device:
                self.data[device_id] = {}
                continue

            try:
                self.data[device_id] = _normalize_device_data(
                    device,
                    self._scale,
                    self._level,
                )
            except (IndexError, TypeError, ValueError) as err:
                _LOGGER.error("Error parsing Kaiterra data for %s: %s", device_id, err)
                self.data[device_id] = {}

        async_dispatcher_send(self._hass, DISPATCHER_KAITERRA)


def _build_device_path(device_type: str, device_id: str) -> str:
    """Build the Kaiterra API path for a device."""
    del device_type
    return f"/devices/{device_id}/top"


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
            sensor_data["units"] = unit

        if "aqi" in point:
            sensor_data["aqi"] = point["aqi"]
            if overall_aqi is None or point["aqi"] > overall_aqi:
                overall_aqi = point["aqi"]
                main_pollutant = POLLUTANTS.get(sensor_name)

        normalized[sensor_name] = sensor_data

    if "tvoc" in normalized and "rtvoc" not in normalized:
        normalized["rtvoc"] = dict(normalized["tvoc"])

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
