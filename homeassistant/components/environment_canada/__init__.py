"""The Environment Canada (EC) component."""

from datetime import timedelta
import logging

from env_canada import ECAirQuality, ECRadar, ECWeather

from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_STATION
from .coordinator import ECConfigEntry, ECDataUpdateCoordinator, ECRuntimeData

DEFAULT_RADAR_UPDATE_INTERVAL = timedelta(minutes=5)
DEFAULT_WEATHER_UPDATE_INTERVAL = timedelta(minutes=5)

PLATFORMS = [Platform.CAMERA, Platform.SENSOR, Platform.WEATHER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ECConfigEntry) -> bool:
    """Set up EC as config entry."""
    lat = config_entry.data.get(CONF_LATITUDE)
    lon = config_entry.data.get(CONF_LONGITUDE)
    station = config_entry.data.get(CONF_STATION)
    lang = config_entry.data.get(CONF_LANGUAGE, "English")

    errors = 0

    weather_data = ECWeather(
        station_id=station,
        coordinates=(lat, lon),
        language=lang.lower(),
    )
    weather_coordinator = ECDataUpdateCoordinator(
        hass, config_entry, weather_data, "weather", DEFAULT_WEATHER_UPDATE_INTERVAL
    )
    try:
        await weather_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        errors = errors + 1
        _LOGGER.warning("Unable to retrieve Environment Canada weather")

    radar_data = ECRadar(coordinates=(lat, lon))
    radar_coordinator = ECDataUpdateCoordinator(
        hass, config_entry, radar_data, "radar", DEFAULT_RADAR_UPDATE_INTERVAL
    )
    try:
        await radar_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        errors = errors + 1
        _LOGGER.warning("Unable to retrieve Environment Canada radar")

    aqhi_data = ECAirQuality(coordinates=(lat, lon))
    aqhi_coordinator = ECDataUpdateCoordinator(
        hass, config_entry, aqhi_data, "AQHI", DEFAULT_WEATHER_UPDATE_INTERVAL
    )
    try:
        await aqhi_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        errors = errors + 1
        _LOGGER.warning("Unable to retrieve Environment Canada AQHI")

    if errors == 3:
        raise ConfigEntryNotReady

    config_entry.runtime_data = ECRuntimeData(
        aqhi_coordinator=aqhi_coordinator,
        radar_coordinator=radar_coordinator,
        weather_coordinator=weather_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ECConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
