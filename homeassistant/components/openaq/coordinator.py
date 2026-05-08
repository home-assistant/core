"""Data coordinator for the OpenAQ integration."""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import Any, cast

import httpx
from openaq import AsyncOpenAQ
from openaq.shared.exceptions import APIError, OpenAQError
from openaq.shared.responses import (
    Coordinates,
    Latest,
    Location,
    Parameter,
    ParameterBase,
    Sensor,
)
from openaq.shared.transport import check_response

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import location as location_util

from .const import CONF_LOCATION_ID, DOMAIN, LOGGER

UPDATE_INTERVAL = timedelta(minutes=10)

OPENAQ_UNIT_ALIASES = {
    "µg/m³": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "µg/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "ug/m³": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "ug/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "μg/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "mg/m3": CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
}


@dataclass(slots=True)
class OpenAQMeasurement:
    """Latest OpenAQ measurement for a parameter."""

    parameter: str
    value: float
    unit: str | None


@dataclass(slots=True)
class OpenAQLocationData:
    """Latest OpenAQ data for a configured location."""

    location_id: int
    name: str
    distance_to_home: float | None
    measurements: MappingProxyType[str, OpenAQMeasurement]


@dataclass(slots=True)
class OpenAQRuntimeData:
    """Runtime data for the OpenAQ integration."""

    client: AsyncOpenAQ
    coordinators: dict[str, OpenAQDataUpdateCoordinator]


type OpenAQConfigEntry = ConfigEntry[OpenAQRuntimeData]


class HomeAssistantOpenAQTransport:
    """OpenAQ transport using Home Assistant's shared httpx client."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        """Initialize the transport."""
        self.client = client

    async def send_request(
        self,
        method: str,
        url: str,
        params: httpx.QueryParams | Mapping[str, str | int | float | bool] | None,
        headers: httpx.Headers | Mapping[str, str],
    ) -> httpx.Response:
        """Send a request through Home Assistant's shared httpx client."""
        response = await self.client.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
        )
        return check_response(response)

    async def close(self) -> None:
        """The OpenAQ SDK calls this when closing, but Home Assistant owns the shared httpx client."""


def create_openaq_client(api_key: str, httpx_client: httpx.AsyncClient) -> AsyncOpenAQ:
    """Create an OpenAQ client with a Home Assistant managed transport."""
    return AsyncOpenAQ(
        api_key=api_key,
        # Avoid importing the SDK's private transport type just for this cast.
        transport=cast(Any, HomeAssistantOpenAQTransport(httpx_client)),
    )


async def async_create_openaq_client(hass: HomeAssistant, api_key: str) -> AsyncOpenAQ:
    """Create an OpenAQ client."""
    return create_openaq_client(api_key, get_async_client(hass))


def normalize_parameter(parameter: Parameter | ParameterBase) -> str:
    """Normalize an OpenAQ parameter object to its canonical name."""
    return parameter.name.lower().replace(".", "").replace("_", "")


def _as_float(value: object) -> float | None:
    """Return value as a float when it is a numeric sensor value."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _normalize_unit(unit: object) -> str | None:
    """Normalize an OpenAQ unit string to Home Assistant's canonical unit."""
    if not isinstance(unit, str):
        return None
    return OPENAQ_UNIT_ALIASES.get(unit, unit)


def _distance_to_home(hass: HomeAssistant, location: Location) -> float | None:
    """Return the distance in meters from Home Assistant to the OpenAQ location."""
    coordinates: Coordinates = location.coordinates
    latitude = _as_float(coordinates.latitude)
    longitude = _as_float(coordinates.longitude)
    if latitude is None or longitude is None:
        return None
    return location_util.distance(
        hass.config.latitude,
        hass.config.longitude,
        latitude,
        longitude,
    )


def _sensor_metadata_by_id(
    sensors: Sequence[Sensor],
) -> dict[int, tuple[str, str | None]]:
    """Return parameter metadata keyed by OpenAQ sensor id."""
    metadata: dict[int, tuple[str, str | None]] = {}
    for sensor in sensors:
        parameter = sensor.parameter
        parameter_name = normalize_parameter(parameter)
        metadata[sensor.id] = (
            parameter_name,
            _normalize_unit(parameter.units),
        )
    return metadata


def normalize_latest_measurements(
    latest_results: Sequence[Latest], sensors: Sequence[Sensor]
) -> MappingProxyType[str, OpenAQMeasurement]:
    """Normalize OpenAQ latest measurements by parameter name."""
    sensor_metadata = _sensor_metadata_by_id(sensors)
    measurements: dict[str, OpenAQMeasurement] = {}

    for latest in latest_results:
        value = _as_float(latest.value)
        if value is None or latest.sensors_id not in sensor_metadata:
            continue
        parameter, unit = sensor_metadata[latest.sensors_id]
        measurements[parameter] = OpenAQMeasurement(parameter, value, unit)

    return MappingProxyType(measurements)


class OpenAQDataUpdateCoordinator(DataUpdateCoordinator[OpenAQLocationData]):
    """Coordinator for fetching OpenAQ location data."""

    config_entry: OpenAQConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenAQConfigEntry,
        subentry: ConfigSubentry,
        client: AsyncOpenAQ,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{subentry.subentry_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.subentry = subentry
        self.location_id: int = subentry.data[CONF_LOCATION_ID]
        self._location: Location | None = None
        self._sensors: Sequence[Sensor] | None = None

    async def _async_update_data(self) -> OpenAQLocationData:
        """Fetch data from OpenAQ."""
        location: Location
        sensors: Sequence[Sensor]
        try:
            if self._location is None or self._sensors is None:
                (
                    location_response,
                    latest_response,
                    sensors_response,
                ) = await asyncio.gather(
                    self.client.locations.get(self.location_id),
                    self.client.locations.latest(self.location_id),
                    self.client.locations.sensors(self.location_id),
                )
                if not location_response.results:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="unable_to_fetch",
                    )
                location = location_response.results[0]
                sensors = sensors_response.results
                self._location = location
                self._sensors = sensors
            else:
                location = self._location
                sensors = self._sensors
                latest_response = await self.client.locations.latest(self.location_id)
        except (APIError, OpenAQError, httpx.HTTPError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
            ) from err

        measurements = normalize_latest_measurements(latest_response.results, sensors)
        return OpenAQLocationData(
            location_id=self.location_id,
            name=location.name,
            distance_to_home=_distance_to_home(self.hass, location),
            measurements=measurements,
        )
