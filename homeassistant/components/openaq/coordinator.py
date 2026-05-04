"""Data coordinator for the OpenAQ integration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import Any

from openaq import (
    ApiKeyMissingError,
    AsyncOpenAQ,
    BadGatewayError,
    BadRequestError,
    ForbiddenError,
    GatewayTimeoutError,
    HTTPRateLimitError,
    NotAuthorizedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    TimeoutError as OpenAQTimeoutError,
    ValidationError,
)
from openaq._async.transport import AsyncTransport

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)
from homeassistant.core import HomeAssistant
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


def create_openaq_client(api_key: str) -> AsyncOpenAQ:
    """Create an OpenAQ client with an independent transport."""
    return AsyncOpenAQ(api_key=api_key, transport=AsyncTransport())


async def async_create_openaq_client(hass: HomeAssistant, api_key: str) -> AsyncOpenAQ:
    """Create an OpenAQ client without blocking the event loop."""
    return await hass.async_add_executor_job(create_openaq_client, api_key)


def get_openaq_value(data: object, *names: str) -> Any:
    """Get a value from an SDK object or a dict-like test object."""
    for name in names:
        if isinstance(data, dict) and name in data:
            return data[name]
        if hasattr(data, name):
            return getattr(data, name)
    return None


def _normalize_parameter(parameter: object) -> str | None:
    """Normalize an OpenAQ parameter object to its canonical name."""
    name = get_openaq_value(parameter, "name")
    if isinstance(name, str):
        return name.lower().replace(".", "").replace("_", "")
    return None


def _normalize_sensor_id(value: object) -> int | None:
    """Normalize an OpenAQ sensor id to an integer."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


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


def _coordinate_value(coordinates: object, name: str) -> float | None:
    """Return a numeric coordinate value."""
    value = get_openaq_value(coordinates, name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _distance_to_home(hass: HomeAssistant, location: object) -> float | None:
    """Return the distance in meters from Home Assistant to the OpenAQ location."""
    coordinates = get_openaq_value(location, "coordinates")
    latitude = _coordinate_value(coordinates, "latitude")
    longitude = _coordinate_value(coordinates, "longitude")
    if latitude is None or longitude is None:
        return None
    return location_util.distance(
        hass.config.latitude,
        hass.config.longitude,
        latitude,
        longitude,
    )


def _sensor_metadata_by_id(
    sensors: Sequence[object],
) -> dict[int, tuple[str, str | None]]:
    """Return parameter metadata keyed by OpenAQ sensor id."""
    metadata: dict[int, tuple[str, str | None]] = {}
    for sensor in sensors:
        sensor_id = _normalize_sensor_id(get_openaq_value(sensor, "id"))
        parameter = get_openaq_value(sensor, "parameter")
        parameter_name = _normalize_parameter(parameter)
        if sensor_id is None or parameter_name is None:
            continue
        metadata[sensor_id] = (
            parameter_name,
            _normalize_unit(get_openaq_value(parameter, "units")),
        )
    return metadata


def normalize_latest_measurements(
    latest_results: Sequence[object], sensors: Sequence[object]
) -> MappingProxyType[str, OpenAQMeasurement]:
    """Normalize OpenAQ latest measurements by parameter name."""
    sensor_metadata = _sensor_metadata_by_id(sensors)
    measurements: dict[str, OpenAQMeasurement] = {}

    for latest in latest_results:
        sensor_id = _normalize_sensor_id(
            get_openaq_value(latest, "sensors_id", "sensorsId")
        )
        value = _as_float(get_openaq_value(latest, "value"))
        if sensor_id is None or value is None:
            continue
        if sensor_id not in sensor_metadata:
            continue
        parameter, unit = sensor_metadata[sensor_id]
        measurements[parameter] = OpenAQMeasurement(parameter, value, unit)

    for sensor in sensors:
        parameter = get_openaq_value(sensor, "parameter")
        parameter_name = _normalize_parameter(parameter)
        latest = get_openaq_value(sensor, "latest")
        value = (
            _as_float(get_openaq_value(latest, "value")) if latest is not None else None
        )
        if parameter_name is None or parameter_name in measurements or value is None:
            continue
        measurements[parameter_name] = OpenAQMeasurement(
            parameter_name,
            value,
            _normalize_unit(get_openaq_value(parameter, "units")),
        )

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

    async def _async_update_data(self) -> OpenAQLocationData:
        """Fetch data from OpenAQ."""
        try:
            location_response = await self.client.locations.get(self.location_id)
            latest_response = await self.client.locations.latest(self.location_id)
            sensors_response = await self.client.locations.sensors(self.location_id)
        except (
            BadGatewayError,
            BadRequestError,
            ApiKeyMissingError,
            ForbiddenError,
            GatewayTimeoutError,
            HTTPRateLimitError,
            NotFoundError,
            NotAuthorizedError,
            OpenAQTimeoutError,
            RateLimitError,
            ServerError,
            ServiceUnavailableError,
            ValidationError,
        ) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
            ) from err

        if not location_response.results:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
            )

        location = location_response.results[0]
        measurements = normalize_latest_measurements(
            latest_response.results, sensors_response.results
        )
        return OpenAQLocationData(
            location_id=self.location_id,
            name=str(get_openaq_value(location, "name")),
            distance_to_home=_distance_to_home(self.hass, location),
            measurements=measurements,
        )


__all__ = [
    "OpenAQConfigEntry",
    "OpenAQDataUpdateCoordinator",
    "OpenAQLocationData",
    "OpenAQMeasurement",
    "OpenAQRuntimeData",
    "async_create_openaq_client",
    "create_openaq_client",
    "get_openaq_value",
    "normalize_latest_measurements",
]
