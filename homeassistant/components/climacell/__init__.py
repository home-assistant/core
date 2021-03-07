"""The ClimaCell integration."""
import asyncio
from datetime import timedelta
import logging
from math import ceil
from typing import Any, Dict, Optional, Union

from pyclimacell import ClimaCellV3, ClimaCellV4
from pyclimacell.const import (
    CURRENT,
    DAILY,
    FORECAST_DAILY,
    FORECAST_HOURLY,
    FORECAST_NOWCAST,
    FORECASTS,
    HOURLY,
    NOWCAST,
    REALTIME,
)
from pyclimacell.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTRIBUTION,
    CC_ATTR_CONDITION,
    CC_ATTR_HUMIDITY,
    CC_ATTR_OZONE,
    CC_ATTR_PRECIPITATION,
    CC_ATTR_PRECIPITATION_PROBABILITY,
    CC_ATTR_PRESSURE,
    CC_ATTR_TEMPERATURE,
    CC_ATTR_TEMPERATURE_HIGH,
    CC_ATTR_TEMPERATURE_LOW,
    CC_ATTR_VISIBILITY,
    CC_ATTR_WIND_DIRECTION,
    CC_ATTR_WIND_SPEED,
    CONF_TIMESTEP,
    DEFAULT_FORECAST_TYPE,
    DEFAULT_TIMESTEP,
    DOMAIN,
    MAX_REQUESTS_PER_DAY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [WEATHER_DOMAIN]


def _set_update_interval(
    hass: HomeAssistantType, current_entry: ConfigEntry
) -> timedelta:
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


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the ClimaCell API component."""
    return True


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

    api_class = ClimaCellV3 if config_entry.data[CONF_API_VERSION] == 3 else ClimaCellV4
    api = api_class(
        config_entry.data[CONF_API_KEY],
        config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
        config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
        session=async_get_clientsession(hass),
    )

    coordinator = ClimaCellDataUpdateCoordinator(
        hass,
        config_entry,
        api,
        _set_update_interval(hass, config_entry),
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

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


async def async_migrate_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Migrate old entry."""
    version = config_entry.version

    _LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Added new config key to support multiple API versions and limited nowcast timesteps
    if version == 1:
        params = {}

        # Add API version if not found
        if CONF_API_VERSION not in config_entry.data:
            new_data = config_entry.data.copy()
            new_data[CONF_API_VERSION] = 3
            params["data"] = new_data

        # Use valid timestep if it's invalid
        timestep = config_entry.options[CONF_TIMESTEP]
        if timestep not in (1, 5, 15, 30):
            if timestep <= 2:
                timestep = 1
            elif timestep <= 7:
                timestep = 5
            elif timestep <= 20:
                timestep = 15
            else:
                timestep = 30
            new_options = config_entry.options.copy()
            new_options[CONF_TIMESTEP] = timestep
            params["options"] = new_options

        version = config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, **params)

    _LOGGER.info("Migration to version %s successful", version)

    return True


class ClimaCellDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold ClimaCell data."""

    def __init__(
        self,
        hass: HomeAssistantType,
        config_entry: ConfigEntry,
        api: Union[ClimaCellV3, ClimaCellV4],
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

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via library."""
        data = {FORECASTS: {}}
        try:
            if self._api_version == 3:
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
        forecast_type: str,
        api_version: int,
    ) -> None:
        """Initialize ClimaCell Entity."""
        super().__init__(coordinator)
        self.api_version = api_version
        self.forecast_type = forecast_type
        self._config_entry = config_entry

    @staticmethod
    def _get_cc_value(
        weather_dict: Dict[str, Any], key: str
    ) -> Optional[Union[int, float, str]]:
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
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        if self.forecast_type == DEFAULT_FORECAST_TYPE:
            return True

        return False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._config_entry.data[CONF_NAME]} - {self.forecast_type.title()}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return f"{self._config_entry.unique_id}_{self.forecast_type}"

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device registry information."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.data[CONF_API_KEY])},
            "name": "ClimaCell",
            "manufacturer": "ClimaCell",
            "sw_version": "v3",
            "entry_type": "service",
        }
