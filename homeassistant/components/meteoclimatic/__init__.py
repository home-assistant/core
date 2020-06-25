"""Support for Meteoclimatic weather data."""
import asyncio
import logging

from meteoclimatic import MeteoclimaticClient
from meteoclimatic.exceptions import MeteoclimaticError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_STATION_CODE,
    DOMAIN,
    METEOCLIMATIC_COORDINATOR,
    METEOCLIMATIC_STATION_CODE,
    METEOCLIMATIC_STATION_NAME,
    METEOCLIMATIC_UPDATER,
    PLATFORMS,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STATION_CODE_SCHEMA = vol.Schema({vol.Required(CONF_STATION_CODE): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [STATION_CODE_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up Meteoclimatic weather platform."""

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for station_code_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=station_code_conf.copy()
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up a Meteoclimatic entry."""

    station_code = entry.data[CONF_STATION_CODE]
    meteoclimatic_updater = MeteoclimaticUpdater(hass, station_code)
    await meteoclimatic_updater.async_update()
    meteoclimatic_data = meteoclimatic_updater.get_data()
    if meteoclimatic_data is None:
        raise ConfigEntryNotReady()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Meteoclimatic Coordinator for {station_code}",
        update_method=meteoclimatic_updater.async_update,
        update_interval=SCAN_INTERVAL,
    )

    meteoclimatic_hass_data = hass.data.setdefault(DOMAIN, {})
    meteoclimatic_hass_data[entry.entry_id] = {
        METEOCLIMATIC_COORDINATOR: coordinator,
        METEOCLIMATIC_STATION_CODE: meteoclimatic_data.station.code,
        METEOCLIMATIC_STATION_NAME: meteoclimatic_data.station.name,
        METEOCLIMATIC_UPDATER: meteoclimatic_updater,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    _LOGGER.debug("meteoclimatic sensor platform loaded for %s", station_code)
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


class MeteoclimaticUpdater:
    """Get data from Meteclimatic weather service."""

    def __init__(self, hass: HomeAssistantType, station_code: str):
        """Initialize the data object."""
        self._hass = hass
        self._data = None
        self._client = MeteoclimaticClient()
        self._station_code = station_code

    def get_data(self):
        """Return the latest data from Meteoclimatic."""
        return self._data

    async def async_update(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        """Obtain the latest data from Meteoclimatic."""
        try:
            self._data = self._client.weather_at_station(self._station_code)
        except MeteoclimaticError as err:
            raise UpdateFailed(err)
