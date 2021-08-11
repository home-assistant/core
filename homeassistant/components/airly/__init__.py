"""The Airly integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from math import ceil

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
from airly import Airly
from airly.exceptions import AirlyError
import async_timeout

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import async_get_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_API_ADVICE,
    ATTR_API_CAQI,
    ATTR_API_CAQI_DESCRIPTION,
    ATTR_API_CAQI_LEVEL,
    CONF_USE_NEAREST,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    NO_AIRLY_SENSORS,
)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


def set_update_interval(instances_count: int, requests_remaining: int) -> timedelta:
    """
    Return data update interval.

    The number of requests is reset at midnight UTC so we calculate the update
    interval based on number of minutes until midnight, the number of Airly instances
    and the number of remaining requests.
    """
    now = dt_util.utcnow()
    midnight = dt_util.find_next_time_expression_time(
        now, seconds=[0], minutes=[0], hours=[0]
    )
    minutes_to_midnight = (midnight - now).total_seconds() / 60
    interval = timedelta(
        minutes=min(
            max(
                ceil(minutes_to_midnight / requests_remaining * instances_count),
                MIN_UPDATE_INTERVAL,
            ),
            MAX_UPDATE_INTERVAL,
        )
    )

    _LOGGER.debug("Data will be update every %s", interval)

    return interval


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Airly as config entry."""
    api_key = entry.data[CONF_API_KEY]
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    use_nearest = entry.data.get(CONF_USE_NEAREST, False)

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=f"{latitude}-{longitude}"
        )

    # identifiers in device_info should use tuple[str, str] type, but latitude and
    # longitude are float, so we convert old device entries to use correct types
    # We used to use a str 3-tuple here sometime, convert that to a 2-tuple too.
    device_registry = await async_get_registry(hass)
    old_ids = (DOMAIN, latitude, longitude)
    for old_ids in (
        (DOMAIN, latitude, longitude),
        (
            DOMAIN,
            str(latitude),
            str(longitude),
        ),
    ):
        device_entry = device_registry.async_get_device({old_ids})  # type: ignore[arg-type]
        if device_entry and entry.entry_id in device_entry.config_entries:
            new_ids = (DOMAIN, f"{latitude}-{longitude}")
            device_registry.async_update_device(
                device_entry.id, new_identifiers={new_ids}
            )

    websession = async_get_clientsession(hass)

    update_interval = timedelta(minutes=MIN_UPDATE_INTERVAL)

    coordinator = AirlyDataUpdateCoordinator(
        hass, websession, api_key, latitude, longitude, update_interval, use_nearest
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # Remove air_quality entities from registry if they exist
    ent_reg = entity_registry.async_get(hass)
    unique_id = f"{coordinator.latitude}-{coordinator.longitude}"
    if entity_id := ent_reg.async_get_entity_id(
        AIR_QUALITY_PLATFORM, DOMAIN, unique_id
    ):
        _LOGGER.debug("Removing deprecated air_quality entity %s", entity_id)
        ent_reg.async_remove(entity_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AirlyDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Airly data."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        api_key: str,
        latitude: float,
        longitude: float,
        update_interval: timedelta,
        use_nearest: bool,
    ) -> None:
        """Initialize."""
        self.latitude = latitude
        self.longitude = longitude
        self.airly = Airly(api_key, session)
        self.use_nearest = use_nearest

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[str, str | float | int]:
        """Update data via library."""
        data: dict[str, str | float | int] = {}
        if self.use_nearest:
            measurements = self.airly.create_measurements_session_nearest(
                self.latitude, self.longitude, max_distance_km=5
            )
        else:
            measurements = self.airly.create_measurements_session_point(
                self.latitude, self.longitude
            )
        with async_timeout.timeout(20):
            try:
                await measurements.update()
            except (AirlyError, ClientConnectorError) as error:
                raise UpdateFailed(error) from error

        _LOGGER.debug(
            "Requests remaining: %s/%s",
            self.airly.requests_remaining,
            self.airly.requests_per_day,
        )

        # Airly API sometimes returns None for requests remaining so we update
        # update_interval only if we have valid value.
        if self.airly.requests_remaining:
            self.update_interval = set_update_interval(
                len(self.hass.config_entries.async_entries(DOMAIN)),
                self.airly.requests_remaining,
            )

        values = measurements.current["values"]
        index = measurements.current["indexes"][0]
        standards = measurements.current["standards"]

        if index["description"] == NO_AIRLY_SENSORS:
            raise UpdateFailed("Can't retrieve data: no Airly sensors in this area")
        for value in values:
            data[value["name"]] = value["value"]
        for standard in standards:
            data[f"{standard['pollutant']}_LIMIT"] = standard["limit"]
            data[f"{standard['pollutant']}_PERCENT"] = standard["percent"]
        data[ATTR_API_CAQI] = index["value"]
        data[ATTR_API_CAQI_LEVEL] = index["level"].lower().replace("_", " ")
        data[ATTR_API_CAQI_DESCRIPTION] = index["description"]
        data[ATTR_API_ADVICE] = index["advice"]
        return data
