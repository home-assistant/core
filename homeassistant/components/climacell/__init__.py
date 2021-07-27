"""The ClimaCell integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from math import ceil
from typing import Any

from pyclimacell import ClimaCellV3, ClimaCellV4
from pyclimacell.const import CURRENT, DAILY, FORECASTS, HOURLY, NOWCAST
from pyclimacell.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTRIBUTION,
    CC_ATTR_CLOUD_COVER,
    CC_ATTR_CONDITION,
    CC_ATTR_HUMIDITY,
    CC_ATTR_OZONE,
    CC_ATTR_PRECIPITATION,
    CC_ATTR_PRECIPITATION_PROBABILITY,
    CC_ATTR_PRECIPITATION_TYPE,
    CC_ATTR_PRESSURE,
    CC_ATTR_TEMPERATURE,
    CC_ATTR_TEMPERATURE_HIGH,
    CC_ATTR_TEMPERATURE_LOW,
    CC_ATTR_VISIBILITY,
    CC_ATTR_WIND_DIRECTION,
    CC_ATTR_WIND_GUST,
    CC_ATTR_WIND_SPEED,
    CC_SENSOR_TYPES,
    CC_V3_ATTR_CLOUD_COVER,
    CC_V3_ATTR_CONDITION,
    CC_V3_ATTR_HUMIDITY,
    CC_V3_ATTR_OZONE,
    CC_V3_ATTR_PRECIPITATION,
    CC_V3_ATTR_PRECIPITATION_DAILY,
    CC_V3_ATTR_PRECIPITATION_PROBABILITY,
    CC_V3_ATTR_PRECIPITATION_TYPE,
    CC_V3_ATTR_PRESSURE,
    CC_V3_ATTR_TEMPERATURE,
    CC_V3_ATTR_VISIBILITY,
    CC_V3_ATTR_WIND_DIRECTION,
    CC_V3_ATTR_WIND_GUST,
    CC_V3_ATTR_WIND_SPEED,
    CC_V3_SENSOR_TYPES,
    CONF_TIMESTEP,
    DEFAULT_TIMESTEP,
    DOMAIN,
    MAX_REQUESTS_PER_DAY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [SENSOR_DOMAIN, WEATHER_DOMAIN]


def _set_update_interval(hass: HomeAssistant, current_entry: ConfigEntry) -> timedelta:
    """Recalculate update_interval based on existing ClimaCell instances and update them."""
    api_calls = 4 if current_entry.data[CONF_API_VERSION] == 3 else 2
    # We check how many ClimaCell configured instances are using the same API key and
    # calculate interval to not exceed allowed numbers of requests. Divide 90% of
    # MAX_REQUESTS_PER_DAY by 4 because every update requires four API calls and we want
    # a buffer in the number of API calls left at the end of the day.
    other_instance_entry_ids = [
        entry.entry_id
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != current_entry.entry_id
        and entry.data[CONF_API_KEY] == current_entry.data[CONF_API_KEY]
    ]

    interval = timedelta(
        minutes=(
            ceil(
                (24 * 60 * (len(other_instance_entry_ids) + 1) * api_calls)
                / (MAX_REQUESTS_PER_DAY * 0.9)
            )
        )
    )

    for entry_id in other_instance_entry_ids:
        if entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN][entry_id].update_interval = interval

    return interval


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ClimaCell API from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    params = {}
    # If config entry options not set up, set them up
    if not entry.options:
        params["options"] = {
            CONF_TIMESTEP: DEFAULT_TIMESTEP,
        }
    else:
        # Use valid timestep if it's invalid
        timestep = entry.options[CONF_TIMESTEP]
        if timestep not in (1, 5, 15, 30):
            if timestep <= 2:
                timestep = 1
            elif timestep <= 7:
                timestep = 5
            elif timestep <= 20:
                timestep = 15
            else:
                timestep = 30
            new_options = entry.options.copy()
            new_options[CONF_TIMESTEP] = timestep
            params["options"] = new_options
    # Add API version if not found
    if CONF_API_VERSION not in entry.data:
        new_data = entry.data.copy()
        new_data[CONF_API_VERSION] = 3
        params["data"] = new_data

    if params:
        hass.config_entries.async_update_entry(entry, **params)

    api_class = ClimaCellV3 if entry.data[CONF_API_VERSION] == 3 else ClimaCellV4
    api = api_class(
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_LATITUDE, hass.config.latitude),
        entry.data.get(CONF_LONGITUDE, hass.config.longitude),
        session=async_get_clientsession(hass),
    )

    coordinator = ClimaCellDataUpdateCoordinator(
        hass,
        entry,
        api,
        _set_update_interval(hass, entry),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return unload_ok


class ClimaCellDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold ClimaCell data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: ClimaCellV3 | ClimaCellV4,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""

        self._config_entry = config_entry
        self._api_version = config_entry.data[CONF_API_VERSION]
        self._api = api
        self.name = config_entry.data[CONF_NAME]
        self.data = {CURRENT: {}, FORECASTS: {}}

        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.data[CONF_NAME],
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        data = {FORECASTS: {}}
        try:
            if self._api_version == 3:
                data[CURRENT] = await self._api.realtime(
                    [
                        CC_V3_ATTR_TEMPERATURE,
                        CC_V3_ATTR_HUMIDITY,
                        CC_V3_ATTR_PRESSURE,
                        CC_V3_ATTR_WIND_SPEED,
                        CC_V3_ATTR_WIND_DIRECTION,
                        CC_V3_ATTR_CONDITION,
                        CC_V3_ATTR_VISIBILITY,
                        CC_V3_ATTR_OZONE,
                        CC_V3_ATTR_WIND_GUST,
                        CC_V3_ATTR_CLOUD_COVER,
                        CC_V3_ATTR_PRECIPITATION_TYPE,
                        *(sensor_type.field for sensor_type in CC_V3_SENSOR_TYPES),
                    ]
                )
                data[FORECASTS][HOURLY] = await self._api.forecast_hourly(
                    [
                        CC_V3_ATTR_TEMPERATURE,
                        CC_V3_ATTR_WIND_SPEED,
                        CC_V3_ATTR_WIND_DIRECTION,
                        CC_V3_ATTR_CONDITION,
                        CC_V3_ATTR_PRECIPITATION,
                        CC_V3_ATTR_PRECIPITATION_PROBABILITY,
                    ],
                    None,
                    timedelta(hours=24),
                )

                data[FORECASTS][DAILY] = await self._api.forecast_daily(
                    [
                        CC_V3_ATTR_TEMPERATURE,
                        CC_V3_ATTR_WIND_SPEED,
                        CC_V3_ATTR_WIND_DIRECTION,
                        CC_V3_ATTR_CONDITION,
                        CC_V3_ATTR_PRECIPITATION_DAILY,
                        CC_V3_ATTR_PRECIPITATION_PROBABILITY,
                    ],
                    None,
                    timedelta(days=14),
                )

                data[FORECASTS][NOWCAST] = await self._api.forecast_nowcast(
                    [
                        CC_V3_ATTR_TEMPERATURE,
                        CC_V3_ATTR_WIND_SPEED,
                        CC_V3_ATTR_WIND_DIRECTION,
                        CC_V3_ATTR_CONDITION,
                        CC_V3_ATTR_PRECIPITATION,
                    ],
                    None,
                    timedelta(
                        minutes=min(300, self._config_entry.options[CONF_TIMESTEP] * 30)
                    ),
                    self._config_entry.options[CONF_TIMESTEP],
                )
            else:
                return await self._api.realtime_and_all_forecasts(
                    [
                        CC_ATTR_TEMPERATURE,
                        CC_ATTR_HUMIDITY,
                        CC_ATTR_PRESSURE,
                        CC_ATTR_WIND_SPEED,
                        CC_ATTR_WIND_DIRECTION,
                        CC_ATTR_CONDITION,
                        CC_ATTR_VISIBILITY,
                        CC_ATTR_OZONE,
                        CC_ATTR_WIND_GUST,
                        CC_ATTR_CLOUD_COVER,
                        CC_ATTR_PRECIPITATION_TYPE,
                        *(sensor_type.field for sensor_type in CC_SENSOR_TYPES),
                    ],
                    [
                        CC_ATTR_TEMPERATURE_LOW,
                        CC_ATTR_TEMPERATURE_HIGH,
                        CC_ATTR_WIND_SPEED,
                        CC_ATTR_WIND_DIRECTION,
                        CC_ATTR_CONDITION,
                        CC_ATTR_PRECIPITATION,
                        CC_ATTR_PRECIPITATION_PROBABILITY,
                    ],
                )
        except (
            CantConnectException,
            InvalidAPIKeyException,
            RateLimitedException,
            UnknownException,
        ) as error:
            raise UpdateFailed from error

        return data


class ClimaCellEntity(CoordinatorEntity):
    """Base ClimaCell Entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: ClimaCellDataUpdateCoordinator,
        api_version: int,
    ) -> None:
        """Initialize ClimaCell Entity."""
        super().__init__(coordinator)
        self.api_version = api_version
        self._config_entry = config_entry

    @staticmethod
    def _get_cc_value(
        weather_dict: dict[str, Any], key: str
    ) -> int | float | str | None:
        """
        Return property from weather_dict.

        Used for V3 API.
        """
        items = weather_dict.get(key, {})
        # Handle cases where value returned is a list.
        # Optimistically find the best value to return.
        if isinstance(items, list):
            if len(items) == 1:
                return items[0].get("value")
            return next(
                (item.get("value") for item in items if "max" in item),
                next(
                    (item.get("value") for item in items if "min" in item),
                    items[0].get("value", None),
                ),
            )

        return items.get("value")

    def _get_current_property(self, property_name: str) -> int | str | float | None:
        """
        Get property from current conditions.

        Used for V4 API.
        """
        return self.coordinator.data.get(CURRENT, {}).get(property_name)

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.data[CONF_API_KEY])},
            "name": "ClimaCell",
            "manufacturer": "ClimaCell",
            "sw_version": f"v{self.api_version}",
            "entry_type": "service",
        }
