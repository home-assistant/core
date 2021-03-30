"""The ClimaCell integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from math import ceil
from typing import Any

from pyclimacell import ClimaCell
from pyclimacell.const import (
    FORECAST_DAILY,
    FORECAST_HOURLY,
    FORECAST_NOWCAST,
    REALTIME,
)
from pyclimacell.pyclimacell import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTRIBUTION,
    CONF_TIMESTEP,
    CURRENT,
    DAILY,
    DEFAULT_TIMESTEP,
    DOMAIN,
    FORECASTS,
    HOURLY,
    MAX_REQUESTS_PER_DAY,
    NOWCAST,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [WEATHER_DOMAIN]


def _set_update_interval(
    hass: HomeAssistantType, current_entry: ConfigEntry
) -> timedelta:
    """Recalculate update_interval based on existing ClimaCell instances and update them."""
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
                (24 * 60 * (len(other_instance_entry_ids) + 1) * 4)
                / (MAX_REQUESTS_PER_DAY * 0.9)
            )
        )
    )

    for entry_id in other_instance_entry_ids:
        if entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN][entry_id].update_interval = interval

    return interval


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Set up ClimaCell API from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # If config entry options not set up, set them up
    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                CONF_TIMESTEP: DEFAULT_TIMESTEP,
            },
        )

    coordinator = ClimaCellDataUpdateCoordinator(
        hass,
        config_entry,
        ClimaCell(
            config_entry.data[CONF_API_KEY],
            config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
            config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
            session=async_get_clientsession(hass),
        ),
        _set_update_interval(hass, config_entry),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return unload_ok


class ClimaCellDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold ClimaCell data."""

    def __init__(
        self,
        hass: HomeAssistantType,
        config_entry: ConfigEntry,
        api: ClimaCell,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""

        self._config_entry = config_entry
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
            data[CURRENT] = await self._api.realtime(
                self._api.available_fields(REALTIME)
            )
            data[FORECASTS][HOURLY] = await self._api.forecast_hourly(
                self._api.available_fields(FORECAST_HOURLY),
                None,
                timedelta(hours=24),
            )

            data[FORECASTS][DAILY] = await self._api.forecast_daily(
                self._api.available_fields(FORECAST_DAILY), None, timedelta(days=14)
            )

            data[FORECASTS][NOWCAST] = await self._api.forecast_nowcast(
                self._api.available_fields(FORECAST_NOWCAST),
                None,
                timedelta(
                    minutes=min(300, self._config_entry.options[CONF_TIMESTEP] * 30)
                ),
                self._config_entry.options[CONF_TIMESTEP],
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
        self, config_entry: ConfigEntry, coordinator: ClimaCellDataUpdateCoordinator
    ) -> None:
        """Initialize ClimaCell Entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry

    @staticmethod
    def _get_cc_value(
        weather_dict: dict[str, Any], key: str
    ) -> int | float | str | None:
        """Return property from weather_dict."""
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

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._config_entry.data[CONF_NAME]

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return self._config_entry.unique_id

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device registry information."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.data[CONF_API_KEY])},
            "name": "ClimaCell",
            "manufacturer": "ClimaCell",
            "sw_version": "v3",
            "entry_type": "service",
        }
