"""Data coordinator for the OpenAQ integration."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import override

from openaq import OpenAQ
from openaq.core.responses import Latest, Location, Parameter, ParameterBase, Sensor

from homeassistant.components.sensor import DEVICE_CLASS_UNITS
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import UnitOfDensity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LOCATION_ID,
    DOMAIN,
    LOGGER,
    OPENAQ_API_EXCEPTIONS,
    OPENAQ_AUTH_EXCEPTIONS,
    OPENAQ_RATE_LIMIT_EXCEPTIONS,
    PARAMETER_DEVICE_CLASSES,
)

UPDATE_INTERVAL = timedelta(minutes=10)

OPENAQ_FETCH_EXCEPTIONS = (
    OPENAQ_AUTH_EXCEPTIONS + OPENAQ_RATE_LIMIT_EXCEPTIONS + OPENAQ_API_EXCEPTIONS
)

OPENAQ_UNIT_ALIASES = {
    "µg/m³": UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    "µg/m3": UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    "ug/m³": UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    "ug/m3": UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    "μg/m³": UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    "μg/m3": UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    "mg/m³": UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
    "mg/m3": UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
}


@dataclass(slots=True)
class OpenAQLocationData:
    """Latest OpenAQ data for a configured location."""

    location_id: int
    name: str
    sensor_metadata: MappingProxyType[str, str]
    measurements: MappingProxyType[str, float]


@dataclass(slots=True)
class OpenAQRuntimeData:
    """Runtime data for the OpenAQ integration."""

    client: OpenAQ
    client_lock: asyncio.Lock
    coordinators: dict[str, OpenAQDataUpdateCoordinator]


type OpenAQConfigEntry = ConfigEntry[OpenAQRuntimeData]


def create_openaq_client(api_key: str) -> OpenAQ:
    """Create an OpenAQ client."""
    return OpenAQ(api_key=api_key, auto_wait=False)


def normalize_parameter(parameter: Parameter | ParameterBase) -> str:
    """Normalize an OpenAQ parameter object to its canonical name."""
    return parameter.name.lower().replace(".", "").replace("_", "")


def _build_sensor_metadata(
    sensors: Sequence[Sensor],
) -> tuple[dict[int, str], MappingProxyType[str, str]]:
    """Return sensor parameter name and unit mappings keyed by sensor id."""
    by_id: dict[int, str] = {}
    units: dict[str, str] = {}

    for sensor in sensors:
        parameter = normalize_parameter(sensor.parameter)
        if parameter not in PARAMETER_DEVICE_CLASSES:
            continue
        unit = OPENAQ_UNIT_ALIASES.get(sensor.parameter.units, sensor.parameter.units)
        device_class = PARAMETER_DEVICE_CLASSES[parameter]
        if device_class is not None:
            valid_units = DEVICE_CLASS_UNITS.get(device_class)
            if valid_units is not None and unit not in valid_units:
                continue
        by_id[sensor.id] = parameter
        units[parameter] = unit

    return by_id, MappingProxyType(units)


def normalize_latest_measurements(
    latest_results: Sequence[Latest],
    sensors_by_id: dict[int, str],
) -> MappingProxyType[str, float]:
    """Normalize OpenAQ latest measurements by parameter name."""
    measurements: dict[str, float] = {}

    for latest in latest_results:
        if latest.sensors_id not in sensors_by_id:
            continue
        parameter = sensors_by_id[latest.sensors_id]
        measurements[parameter] = latest.value

    return MappingProxyType(measurements)


def _fetch_initial_location_data(
    client: OpenAQ, location_id: int
) -> tuple[Sequence[Location], Sequence[Latest], Sequence[Sensor]]:
    """Fetch all SDK data required for an initial location refresh."""
    return (
        client.locations.get(location_id).results,
        client.locations.latest(location_id).results,
        client.locations.sensors(location_id).results,
    )


class OpenAQDataUpdateCoordinator(DataUpdateCoordinator[OpenAQLocationData]):
    """Coordinator for fetching OpenAQ location data."""

    config_entry: OpenAQConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenAQConfigEntry,
        subentry: ConfigSubentry,
        client: OpenAQ,
        client_lock: asyncio.Lock,
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
        self._client_lock = client_lock
        self.subentry = subentry
        self.location_id: int = subentry.data[CONF_LOCATION_ID]
        self._location: Location | None = None
        self._sensors_by_id: dict[int, str] | None = None
        self._sensor_metadata: MappingProxyType[str, str] | None = None

    @override
    async def _async_update_data(self) -> OpenAQLocationData:
        """Fetch data from OpenAQ."""
        if self._location is None:
            async with self._client_lock:
                try:
                    (
                        location_results,
                        latest_results,
                        sensors,
                    ) = await self.hass.async_add_executor_job(
                        _fetch_initial_location_data, self.client, self.location_id
                    )
                except OPENAQ_FETCH_EXCEPTIONS as err:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="unable_to_fetch",
                    ) from err
            if not location_results:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_fetch",
                )
            self._location = location_results[0]
            self._sensors_by_id, self._sensor_metadata = _build_sensor_metadata(sensors)
        else:
            async with self._client_lock:
                try:
                    latest_results = (
                        await self.hass.async_add_executor_job(
                            self.client.locations.latest, self.location_id
                        )
                    ).results
                except OPENAQ_FETCH_EXCEPTIONS as err:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="unable_to_fetch",
                    ) from err

        assert self._sensors_by_id is not None
        assert self._sensor_metadata is not None
        measurements = normalize_latest_measurements(
            latest_results, self._sensors_by_id
        )
        return OpenAQLocationData(
            location_id=self.location_id,
            name=self._location.name,
            sensor_metadata=self._sensor_metadata,
            measurements=measurements,
        )
