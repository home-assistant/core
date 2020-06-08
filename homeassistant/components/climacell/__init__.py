"""The ClimaCell integration."""
import asyncio
from datetime import timedelta
import logging
from math import ceil
from typing import Any, Dict

from pyclimacell.const import FORECAST_DAILY, FORECAST_HOURLY, REALTIME
from pyclimacell.pyclimacell import (
    CantConnectException,
    ClimaCell,
    InvalidAPIKeyException,
    RateLimitedException,
)
import voluptuous as vol

from homeassistant.components.air_quality import DOMAIN as AQ_DOMAIN
from homeassistant.components.weather import DOMAIN as W_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CHINA,
    CONF_AQI_COUNTRY,
    CONF_FORECAST_FREQUENCY,
    CURRENT,
    DAILY,
    DEFAULT_NAME,
    DISABLE_FORECASTS,
    DOMAIN,
    FORECASTS,
    HOURLY,
    MAX_REQUESTS_PER_DAY,
    USA,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Inclusive(CONF_LATITUDE, "location"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "location"): cv.longitude,
        vol.Optional(CONF_FORECAST_FREQUENCY, default=DAILY): vol.In(
            (DISABLE_FORECASTS, DAILY, HOURLY)
        ),
        vol.Optional(CONF_AQI_COUNTRY, default=USA): vol.In((USA, CHINA)),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [SCHEMA])}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = [AQ_DOMAIN, W_DOMAIN]


def set_update_interval(
    hass: HomeAssistantType, current_entry: ConfigEntry
) -> timedelta:
    """Recalculate update_interval based on existing ClimaCell instances and update them."""
    # We check how many ClimaCell configured instances are using the same API key and calculate
    # interval to not exceed allowed numbers of requests. Divide MAX_REQUESTS_PER_DAY by 2
    # because every update requires two API calls.
    entries = hass.config_entries.async_entries(DOMAIN)
    other_instance_entry_ids = []
    for entry in entries:
        if (
            entry.entry_id != current_entry.entry_id
            and current_entry.data[CONF_API_KEY] == entry.data[CONF_API_KEY]
        ):
            other_instance_entry_ids.append(entry.entry_id)
    interval = timedelta(
        minutes=(
            ceil(24 * 60 / MAX_REQUESTS_PER_DAY / 2)
            * (len(other_instance_entry_ids) + 1)
        )
    )

    if len(other_instance_entry_ids) > 0:
        for entry_id in other_instance_entry_ids:
            hass.data[DOMAIN][entry_id].update_interval = interval

    return interval


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the ClimaCell API component."""
    if DOMAIN in config:
        for config_entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=config_entry
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Set up ClimaCell API from a config entry."""
    coordinator = ClimaCellDataUpdateCoordinator(
        hass,
        config_entry,
        ClimaCell(
            config_entry.data[CONF_API_KEY],
            config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
            config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
            session=async_get_clientsession(hass),
        ),
        set_update_interval(hass, config_entry),
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
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
        self._forecast_frequency = config_entry.data.get(CONF_FORECAST_FREQUENCY)
        self.name = config_entry.data[CONF_NAME]
        self.data = {CURRENT: {}, FORECASTS: []}

        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.data[CONF_NAME],
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via library."""
        data = {}
        try:
            data[CURRENT] = await self._api.realtime(
                self._api.availabile_fields(REALTIME)
            )

            if self._forecast_frequency == HOURLY.lower():
                data[FORECASTS] = await self._api.forecast_hourly(
                    self._api.availabile_fields(FORECAST_HOURLY),
                    None,
                    timedelta(hours=90),
                )

            if self._forecast_frequency == DAILY.lower():
                data[FORECASTS] = await self._api.forecast_daily(
                    self._api.availabile_fields(FORECAST_DAILY),
                    None,
                    timedelta(days=14),
                )

            return data
        except (
            CantConnectException,
            InvalidAPIKeyException,
            RateLimitedException,
        ) as error:
            raise UpdateFailed(error)
