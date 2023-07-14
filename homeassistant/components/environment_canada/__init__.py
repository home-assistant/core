"""The Environment Canada (EC) component."""
from datetime import timedelta
import logging
import xml.etree.ElementTree as et

from env_canada import ECAirQuality, ECRadar, ECWeather, ec_exc

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LANGUAGE, CONF_STATION, DOMAIN

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


class ECDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching EC data."""

    def __init__(self, hass, ec_data, name, update_interval):
        """Initialize global EC data updater."""
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN} {name}", update_interval=update_interval
        )
        self.ec_data = ec_data
        self.last_update_success = False

    async def _async_update_data(self):
        """Fetch data from EC."""
        try:
            await self.ec_data.update()
        except (et.ParseError, ec_exc.UnknownStationId) as ex:
            raise UpdateFailed(f"Error fetching {self.name} data: {ex}") from ex
        return self.ec_data
