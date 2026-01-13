"""The Tomorrow.io integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from math import ceil
from typing import Any

from pytomorrowio import TomorrowioV4
from pytomorrowio.const import CURRENT, FORECASTS
from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    MalformedRequestException,
    RateLimitedException,
    UnknownException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TIMESTEP, DOMAIN, LOGGER, TomorrowioAttr

REALTIME_FIELDS: list[str] = [
    # Weather
    TomorrowioAttr.TEMPERATURE,
    TomorrowioAttr.HUMIDITY,
    TomorrowioAttr.PRESSURE,
    TomorrowioAttr.WIND_SPEED,
    TomorrowioAttr.WIND_DIRECTION,
    TomorrowioAttr.CONDITION,
    TomorrowioAttr.VISIBILITY,
    TomorrowioAttr.OZONE,
    TomorrowioAttr.WIND_GUST,
    TomorrowioAttr.CLOUD_COVER,
    TomorrowioAttr.PRECIPITATION_TYPE,
    # Sensors
    TomorrowioAttr.CARBON_MONOXIDE,
    TomorrowioAttr.CHINA_AQI,
    TomorrowioAttr.CHINA_HEALTH_CONCERN,
    TomorrowioAttr.CHINA_PRIMARY_POLLUTANT,
    TomorrowioAttr.CLOUD_BASE,
    TomorrowioAttr.CLOUD_CEILING,
    TomorrowioAttr.CLOUD_COVER,
    TomorrowioAttr.DEW_POINT,
    TomorrowioAttr.EPA_AQI,
    TomorrowioAttr.EPA_HEALTH_CONCERN,
    TomorrowioAttr.EPA_PRIMARY_POLLUTANT,
    TomorrowioAttr.FEELS_LIKE,
    TomorrowioAttr.FIRE_INDEX,
    TomorrowioAttr.NITROGEN_DIOXIDE,
    TomorrowioAttr.OZONE,
    TomorrowioAttr.PARTICULATE_MATTER_10,
    TomorrowioAttr.PARTICULATE_MATTER_25,
    TomorrowioAttr.POLLEN_GRASS,
    TomorrowioAttr.POLLEN_TREE,
    TomorrowioAttr.POLLEN_WEED,
    TomorrowioAttr.PRECIPITATION_TYPE,
    TomorrowioAttr.PRESSURE_SURFACE_LEVEL,
    TomorrowioAttr.SOLAR_GHI,
    TomorrowioAttr.SULPHUR_DIOXIDE,
    TomorrowioAttr.UV_INDEX,
    TomorrowioAttr.UV_HEALTH_CONCERN,
    TomorrowioAttr.WIND_GUST,
]

ALL_FORECAST_FIELDS: list[str] = [
    TomorrowioAttr.TEMPERATURE_LOW,
    TomorrowioAttr.TEMPERATURE_HIGH,
    TomorrowioAttr.DEW_POINT,
    TomorrowioAttr.HUMIDITY,
    TomorrowioAttr.WIND_SPEED,
    TomorrowioAttr.WIND_DIRECTION,
    TomorrowioAttr.CONDITION,
    TomorrowioAttr.PRECIPITATION,
    TomorrowioAttr.PRECIPITATION_PROBABILITY,
]


@callback
def async_get_entries_by_api_key(
    hass: HomeAssistant, api_key: str, exclude_entry: ConfigEntry | None = None
) -> list[ConfigEntry]:
    """Get all entries for a given API key."""
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data[CONF_API_KEY] == api_key
        and (exclude_entry is None or exclude_entry != entry)
    ]


@callback
def async_set_update_interval(
    hass: HomeAssistant, api: TomorrowioV4, exclude_entry: ConfigEntry | None = None
) -> timedelta:
    """Calculate update_interval."""
    # We check how many Tomorrow.io configured instances are using the same API key and
    # calculate interval to not exceed allowed numbers of requests. Divide 90% of
    # max_requests by the number of API calls because we want a buffer in the
    # number of API calls left at the end of the day.
    entries = async_get_entries_by_api_key(hass, api.api_key, exclude_entry)
    minutes = ceil(
        (24 * 60 * len(entries) * api.num_api_requests)
        / (api.max_requests_per_day * 0.9)
    )
    LOGGER.debug(
        (
            "Number of config entries: %s\n"
            "Number of API Requests per call: %s\n"
            "Max requests per day: %s\n"
            "Update interval: %s minutes"
        ),
        len(entries),
        api.num_api_requests,
        api.max_requests_per_day,
        minutes,
    )
    return timedelta(minutes=minutes)


class TomorrowioDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Define an object to hold Tomorrow.io data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: TomorrowioV4
    ) -> None:
        """Initialize."""
        self._api = api
        self.data = {CURRENT: {}, FORECASTS: {}}
        self.entry_id_to_location_dict: dict[str, str] = {}
        self._coordinator_ready: asyncio.Event | None = None
        self._setup_error: Exception | None = None

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{self._api.api_key_masked}",
        )

    def add_entry_to_location_dict(self, entry: ConfigEntry) -> None:
        """Add an entry to the location dict."""
        latitude = entry.data[CONF_LOCATION][CONF_LATITUDE]
        longitude = entry.data[CONF_LOCATION][CONF_LONGITUDE]
        self.entry_id_to_location_dict[entry.entry_id] = f"{latitude},{longitude}"

    async def async_setup_entry(self, entry: ConfigEntry) -> None:
        """Load config entry into coordinator."""
        # If we haven't loaded any data yet, register all entries with this API key and
        # get the initial data for all of them. We do this because another config entry
        # may start setup before we finish setting the initial data and we don't want
        # to do multiple refreshes on startup.
        if self._coordinator_ready is None:
            LOGGER.debug(
                "Setting up coordinator for API key %s, loading data for all entries",
                self._api.api_key_masked,
            )
            self._coordinator_ready = asyncio.Event()
            for entry_ in async_get_entries_by_api_key(self.hass, self._api.api_key):
                self.add_entry_to_location_dict(entry_)
            LOGGER.debug(
                "Loaded %s entries, initiating first refresh",
                len(self.entry_id_to_location_dict),
            )
            try:
                async with asyncio.timeout(45):
                    await self.async_config_entry_first_refresh()
            except Exception as err:
                self._setup_error = err
                raise ConfigEntryNotReady(str(err)) from err
            finally:
                self._coordinator_ready.set()
        else:
            # If we have an event, we need to wait for it to be set before we proceed
            await self._coordinator_ready.wait()
            if self._setup_error is not None:
                raise ConfigEntryNotReady(str(self._setup_error)) from self._setup_error
            # If we're not getting new data because we already know this entry, we
            # don't need to schedule a refresh
            if entry.entry_id in self.entry_id_to_location_dict:
                return
            LOGGER.debug(
                (
                    "Adding new entry to existing coordinator for API key %s, doing a "
                    "partial refresh"
                ),
                self._api.api_key_masked,
            )
            # We need a refresh, but it's going to be a partial refresh so we can
            # minimize repeat API calls
            self.add_entry_to_location_dict(entry)
            await self.async_refresh()

        self.update_interval = async_set_update_interval(self.hass, self._api)
        self._async_unsub_refresh()
        if self._listeners:
            self._schedule_refresh()

    async def async_unload_entry(self, entry: ConfigEntry) -> bool | None:
        """Unload a config entry from coordinator.

        Returns whether coordinator can be removed as well because there are no
        config entries tied to it anymore.
        """
        self.entry_id_to_location_dict.pop(entry.entry_id)
        self.update_interval = async_set_update_interval(self.hass, self._api, entry)
        return not self.entry_id_to_location_dict

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        data: dict[str, Any] = {}
        # If we are refreshing because of a new config entry that's not already in our
        # data, we do a partial refresh to avoid wasted API calls.
        if self.data and any(
            entry_id not in self.data for entry_id in self.entry_id_to_location_dict
        ):
            data = self.data

        LOGGER.debug(
            "Fetching data for %s entries",
            len(set(self.entry_id_to_location_dict) - set(data)),
        )
        for entry_id, location in self.entry_id_to_location_dict.items():
            if entry_id in data:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            assert entry
            try:
                async with asyncio.timeout(30):
                    data[entry_id] = await self._api.realtime_and_all_forecasts(
                        realtime_fields=REALTIME_FIELDS,
                        all_forecasts_fields=ALL_FORECAST_FIELDS,
                        nowcast_timestep=entry.options[CONF_TIMESTEP],
                        location=location,
                    )
            except MalformedRequestException as err:
                raise UpdateFailed(str(err)) from err
            except (
                CantConnectException,
                InvalidAPIKeyException,
                RateLimitedException,
                UnknownException,
            ) as error:
                raise UpdateFailed from error

        return data
