"""The Environment Canada (EC) component."""

from datetime import timedelta
import logging

from env_canada import ECAirQuality, ECRadar, ECWeather

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import CONF_STATION, DOMAIN
from .coordinator import ECDataUpdateCoordinator

DEFAULT_RADAR_UPDATE_INTERVAL = timedelta(minutes=5)
DEFAULT_WEATHER_UPDATE_INTERVAL = timedelta(minutes=5)

PLATFORMS = [Platform.CAMERA, Platform.SENSOR, Platform.WEATHER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up EC as config entry."""
    lat = config_entry.data.get(CONF_LATITUDE)
    lon = config_entry.data.get(CONF_LONGITUDE)
    station = config_entry.data.get(CONF_STATION)
    lang = config_entry.data.get(CONF_LANGUAGE, "English")

    coordinators = {}
    errors = 0

    weather_data = ECWeather(
        station_id=station,
        coordinates=(lat, lon),
        language=lang.lower(),
    )
    coordinators["weather_coordinator"] = ECDataUpdateCoordinator(
        hass, weather_data, "weather", DEFAULT_WEATHER_UPDATE_INTERVAL
    )
    try:
        await coordinators["weather_coordinator"].async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        errors = errors + 1
        _LOGGER.warning("Unable to retrieve Environment Canada weather")

    radar_data = ECRadar(coordinates=(lat, lon))
    coordinators["radar_coordinator"] = ECDataUpdateCoordinator(
        hass, radar_data, "radar", DEFAULT_RADAR_UPDATE_INTERVAL
    )
    try:
        await coordinators["radar_coordinator"].async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        errors = errors + 1
        _LOGGER.warning("Unable to retrieve Environment Canada radar")

    aqhi_data = ECAirQuality(coordinates=(lat, lon))
    coordinators["aqhi_coordinator"] = ECDataUpdateCoordinator(
        hass, aqhi_data, "AQHI", DEFAULT_WEATHER_UPDATE_INTERVAL
    )
    try:
        await coordinators["aqhi_coordinator"].async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        errors = errors + 1
        _LOGGER.warning("Unable to retrieve Environment Canada AQHI")

    if errors == 3:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


def device_info(config_entry: ConfigEntry) -> DeviceInfo:
    """Build and return the device info for EC."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, config_entry.entry_id)},
        manufacturer="Environment Canada",
        name=config_entry.title,
        configuration_url="https://weather.gc.ca/",
    )
