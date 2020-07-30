"""The ClimaCell integration."""
import asyncio
from datetime import timedelta
import logging
from math import ceil
from typing import Any, Dict

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
import voluptuous as vol

from homeassistant.components.air_quality import DOMAIN as AQ_DOMAIN
from homeassistant.components.weather import DOMAIN as W_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTRIBUTION,
    CHINA,
    CONF_AQI_COUNTRY,
    CONF_FORECAST_TYPE,
    CONF_TIMESTEP,
    CURRENT,
    DAILY,
    DEFAULT_AQI_COUNTRY,
    DEFAULT_FORECAST_TYPE,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DISABLE_FORECASTS,
    DOMAIN,
    FORECASTS,
    HOURLY,
    MAX_REQUESTS_PER_DAY,
    NOWCAST,
    USA,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Inclusive(CONF_LATITUDE, "location"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "location"): cv.longitude,
        vol.Optional(CONF_FORECAST_TYPE, default=DEFAULT_FORECAST_TYPE): vol.In(
            (DISABLE_FORECASTS, DAILY, HOURLY, NOWCAST)
        ),
        vol.Optional(CONF_TIMESTEP, default=DEFAULT_TIMESTEP): vol.All(
            int, vol.Range(1, 60)
        ),
        vol.Optional(CONF_AQI_COUNTRY, default=DEFAULT_AQI_COUNTRY): vol.In(
            (USA, CHINA)
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [SCHEMA])}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = [AQ_DOMAIN, W_DOMAIN]


def _set_update_interval(
    hass: HomeAssistantType, current_entry: ConfigEntry
) -> timedelta:
    """Recalculate update_interval based on existing ClimaCell instances and update them."""
    # We check how many ClimaCell configured instances are using the same API key and
    # calculate interval to not exceed allowed numbers of requests. Divide 90% of
    # MAX_REQUESTS_PER_DAY by 2 because every update requires two API calls and we want
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
                (24 * 60 * (len(other_instance_entry_ids) + 1) * 2)
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
    if DOMAIN in config:
        for climacell_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=climacell_config
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Set up ClimaCell API from a config entry."""
    # If config entry options not set up, set them up
    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                CONF_TIMESTEP: config_entry.data.get(CONF_TIMESTEP, DEFAULT_TIMESTEP),
                CONF_AQI_COUNTRY: config_entry.data.get(
                    CONF_AQI_COUNTRY, DEFAULT_AQI_COUNTRY
                ),
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
        self._forecast_type = config_entry.data[CONF_FORECAST_TYPE]
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
                self._api.available_fields(REALTIME)
            )

            if self._forecast_type == HOURLY:
                data[FORECASTS] = await self._api.forecast_hourly(
                    self._api.available_fields(FORECAST_HOURLY),
                    None,
                    timedelta(hours=24),
                )

            if self._forecast_type == DAILY:
                data[FORECASTS] = await self._api.forecast_daily(
                    self._api.available_fields(FORECAST_DAILY), None, timedelta(days=14)
                )

            if self._forecast_type == NOWCAST:
                data[FORECASTS] = await self._api.forecast_nowcast(
                    self._api.available_fields(FORECAST_NOWCAST),
                    None,
                    timedelta(
                        minutes=min(300, self._config_entry.options[CONF_TIMESTEP] * 30)
                    ),
                    self._config_entry.options[CONF_TIMESTEP],
                )

            return data
        except (
            CantConnectException,
            InvalidAPIKeyException,
            RateLimitedException,
            UnknownException,
        ) as error:
            raise UpdateFailed(error)


class ClimaCellEntity(Entity):
    """Base ClimaCell Entity."""

    def __init__(
        self, config_entry: ConfigEntry, coordinator: ClimaCellDataUpdateCoordinator
    ) -> None:
        """Initialize ClimaCell Entity."""
        self._config_entry = config_entry
        self._coordinator = coordinator
        self._async_unsub_listeners = []

    async def async_update(self) -> None:
        """Retrieve latest state of the device."""
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self._async_unsub_listeners.append(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect callbacks when entity is removed."""
        for listener in self._async_unsub_listeners:
            listener()

        self._async_unsub_listeners.clear()

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def available(self) -> bool:
        """Return the availabiliity of the entity."""
        return self._coordinator.last_update_success

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
    def device_info(self) -> Dict[str, Any]:
        """Return device registry information."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.data[CONF_API_KEY])},
            "name": self.name,
            "manufacturer": "ClimaCell",
            "entry_type": "service",
        }
