"""Data coordinator for the OpenAQ integration."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import NoReturn, TypeVar, override

from openaq import OpenAQ
from openaq.core.responses import Latest, Location, Parameter, ParameterBase, Sensor

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LOCATION_ID,
    DOMAIN,
    LOGGER,
    OPENAQ_AUTH_EXCEPTIONS,
    OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
    OPENAQ_UNIT_MILLIGRAMS_PER_CUBIC_METER,
)

UPDATE_INTERVAL = timedelta(minutes=10)
_T = TypeVar("_T")

OPENAQ_UNIT_ALIASES = {
    "µg/m³": OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
    "µg/m3": OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
    "ug/m³": OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
    "ug/m3": OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
    "μg/m³": OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
    "μg/m3": OPENAQ_UNIT_MICROGRAMS_PER_CUBIC_METER,
    "mg/m³": OPENAQ_UNIT_MILLIGRAMS_PER_CUBIC_METER,
    "mg/m3": OPENAQ_UNIT_MILLIGRAMS_PER_CUBIC_METER,
}


@dataclass(slots=True)
class OpenAQMeasurement:
    """Latest OpenAQ measurement for a parameter."""

    parameter: str
    value: float
    unit: str | None


@dataclass(slots=True)
class OpenAQSensorMetadata:
    """OpenAQ sensor metadata for a parameter."""

    parameter: str
    unit: str | None


@dataclass(slots=True)
class OpenAQLocationData:
    """Latest OpenAQ data for a configured location."""

    location_id: int
    name: str
    sensor_metadata: MappingProxyType[str, OpenAQSensorMetadata]
    measurements: MappingProxyType[str, OpenAQMeasurement]


@dataclass(slots=True)
class OpenAQRuntimeData:
    """Runtime data for the OpenAQ integration."""

    client: OpenAQ
    coordinators: dict[str, OpenAQDataUpdateCoordinator]


type OpenAQConfigEntry = ConfigEntry[OpenAQRuntimeData]


def create_openaq_client(api_key: str) -> OpenAQ:
    """Create an OpenAQ client."""
    return OpenAQ(api_key=api_key)


async def async_create_openaq_client(hass: HomeAssistant, api_key: str) -> OpenAQ:
    """Create an OpenAQ client."""
    return await hass.async_add_executor_job(create_openaq_client, api_key)


def normalize_parameter(parameter: Parameter | ParameterBase) -> str:
    """Normalize an OpenAQ parameter object to its canonical name."""
    return parameter.name.lower().replace(".", "").replace("_", "")


def _normalize_unit(unit: str | None) -> str | None:
    """Normalize an OpenAQ unit string to Home Assistant's canonical unit."""
    if unit is None:
        return None
    return OPENAQ_UNIT_ALIASES.get(unit, unit)


def _sensor_metadata_by_id(
    sensors: Sequence[Sensor],
) -> dict[int, OpenAQSensorMetadata]:
    """Return parameter metadata keyed by OpenAQ sensor id."""
    metadata: dict[int, OpenAQSensorMetadata] = {}
    for sensor in sensors:
        parameter = sensor.parameter
        parameter_name = normalize_parameter(parameter)
        metadata[sensor.id] = OpenAQSensorMetadata(
            parameter=parameter_name,
            unit=_normalize_unit(parameter.units),
        )
    return metadata


def normalize_sensor_metadata(
    sensors: Sequence[Sensor],
) -> MappingProxyType[str, OpenAQSensorMetadata]:
    """Normalize OpenAQ sensor metadata by parameter name."""
    return MappingProxyType(
        {
            metadata.parameter: metadata
            for metadata in _sensor_metadata_by_id(sensors).values()
        }
    )


def normalize_latest_measurements(
    latest_results: Sequence[Latest], sensors: Sequence[Sensor]
) -> MappingProxyType[str, OpenAQMeasurement]:
    """Normalize OpenAQ latest measurements by parameter name."""
    sensor_metadata = _sensor_metadata_by_id(sensors)
    measurements: dict[str, OpenAQMeasurement] = {}

    for latest in latest_results:
        if latest.value is None or latest.sensors_id not in sensor_metadata:
            continue
        metadata = sensor_metadata[latest.sensors_id]
        measurements[metadata.parameter] = OpenAQMeasurement(
            metadata.parameter, float(latest.value), metadata.unit
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
        client: OpenAQ,
        client_lock: asyncio.Lock | None = None,
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
        self._client_lock = client_lock or asyncio.Lock()
        self.subentry = subentry
        self.location_id: int = subentry.data[CONF_LOCATION_ID]
        self._location: Location | None = None
        self._sensors: Sequence[Sensor] | None = None

    async def _async_run_openaq_job(
        self, target: Callable[..., _T], *args: object
    ) -> _T:
        """Run a blocking OpenAQ SDK call."""
        async with self._client_lock:
            return await self.hass.async_add_executor_job(target, *args)

    def _raise_update_failed(self, err: Exception) -> NoReturn:
        """Raise a translated update failure."""
        if isinstance(err, OPENAQ_AUTH_EXCEPTIONS):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="unable_to_fetch",
        ) from err

    @override
    async def _async_update_data(self) -> OpenAQLocationData:
        """Fetch data from OpenAQ."""
        location: Location
        sensors: Sequence[Sensor]
        if self._location is None or self._sensors is None:
            try:
                location_response = await self._async_run_openaq_job(
                    self.client.locations.get, self.location_id
                )
                latest_response = await self._async_run_openaq_job(
                    self.client.locations.latest, self.location_id
                )
                sensors_response = await self._async_run_openaq_job(
                    self.client.locations.sensors, self.location_id
                )
            except Exception as err:  # noqa: BLE001
                self._raise_update_failed(err)
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
            try:
                latest_response = await self._async_run_openaq_job(
                    self.client.locations.latest, self.location_id
                )
            except Exception as err:  # noqa: BLE001
                self._raise_update_failed(err)

        measurements = normalize_latest_measurements(latest_response.results, sensors)
        return OpenAQLocationData(
            location_id=self.location_id,
            name=location.name,
            sensor_metadata=normalize_sensor_metadata(sensors),
            measurements=measurements,
        )
