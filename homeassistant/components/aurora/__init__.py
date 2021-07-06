"""The aurora component."""

from datetime import timedelta
import logging

from aiohttp import ClientError
from auroranoaa import AuroraForecast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_ENTRY_TYPE,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTRIBUTION,
    AURORA_API,
    CONF_THRESHOLD,
    COORDINATOR,
    DEFAULT_POLLING_INTERVAL,
    DEFAULT_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aurora from a config entry."""

    conf = entry.data
    options = entry.options

    session = aiohttp_client.async_get_clientsession(hass)
    api = AuroraForecast(session)

    longitude = conf[CONF_LONGITUDE]
    latitude = conf[CONF_LATITUDE]
    polling_interval = DEFAULT_POLLING_INTERVAL
    threshold = options.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
    name = conf[CONF_NAME]

    coordinator = AuroraDataUpdateCoordinator(
        hass=hass,
        name=name,
        polling_interval=polling_interval,
        api=api,
        latitude=latitude,
        longitude=longitude,
        threshold=threshold,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        AURORA_API: api,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AuroraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the NOAA Aurora API."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        polling_interval: int,
        api: str,
        latitude: float,
        longitude: float,
        threshold: float,
    ) -> None:
        """Initialize the data updater."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(minutes=polling_interval),
        )

        self.api = api
        self.name = name
        self.latitude = int(latitude)
        self.longitude = int(longitude)
        self.threshold = int(threshold)

    async def _async_update_data(self):
        """Fetch the data from the NOAA Aurora Forecast."""

        try:
            return await self.api.get_forecast_data(self.longitude, self.latitude)
        except ClientError as error:
            raise UpdateFailed(f"Error updating from NOAA: {error}") from error


class AuroraEntity(CoordinatorEntity):
    """Implementation of the base Aurora Entity."""

    def __init__(
        self,
        coordinator: AuroraDataUpdateCoordinator,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the Aurora Entity."""

        super().__init__(coordinator=coordinator)

        self._name = name
        self._unique_id = f"{self.coordinator.latitude}_{self.coordinator.longitude}"
        self._icon = icon

    @property
    def unique_id(self):
        """Define the unique id based on the latitude and longitude."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"attribution": ATTRIBUTION}

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return self._icon

    @property
    def device_info(self):
        """Define the device based on name."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._unique_id)},
            ATTR_NAME: self.coordinator.name,
            ATTR_MANUFACTURER: "NOAA",
            ATTR_MODEL: "Aurora Visibility Sensor",
            ATTR_ENTRY_TYPE: "service",
        }
