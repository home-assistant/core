"""The Tesla Powerwall integration."""
import asyncio
from datetime import timedelta
import logging

from tesla_powerwall import (
    ApiError,
    MetersResponse,
    PowerWall,
    PowerWallUnreachableError,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    POWERWALL_API_CHARGE,
    POWERWALL_API_GRID_STATUS,
    POWERWALL_API_METERS,
    POWERWALL_API_SITEMASTER,
    POWERWALL_COORDINATOR,
    POWERWALL_IP_ADDRESS,
    POWERWALL_OBJECT,
    POWERWALL_SITE_INFO,
    POWERWALL_SITE_NAME,
    UPDATE_INTERVAL,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_IP_ADDRESS): cv.string})},
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["binary_sensor", "sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tesla Powerwall component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf,
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tesla Powerwall from a config entry."""

    entry_id = entry.entry_id

    hass.data[DOMAIN].setdefault(entry_id, {})
    power_wall = PowerWall(entry.data[CONF_IP_ADDRESS])

    def _call_site_info(power_wall):
        """Wrap site_info to be a callable."""
        return power_wall.site_info

    site_info = None
    try:
        site_info = await hass.async_add_executor_job(_call_site_info, power_wall)
    except (PowerWallUnreachableError, ApiError, ConnectionError):
        raise ConfigEntryNotReady

    async def async_update_data():
        """Fetch data from API endpoint."""
        return await hass.async_add_executor_job(_fetch_powerwall_data, power_wall)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Powerwall site",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        POWERWALL_OBJECT: power_wall,
        POWERWALL_COORDINATOR: coordinator,
        POWERWALL_SITE_INFO: site_info,
        POWERWALL_IP_ADDRESS: entry.data[CONF_IP_ADDRESS],
    }

    await coordinator.async_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


def _fetch_powerwall_data(power_wall):
    """Process and update powerwall data."""
    meters = power_wall.meters
    return {
        POWERWALL_API_CHARGE: power_wall.charge,
        POWERWALL_API_SITEMASTER: power_wall.sitemaster,
        POWERWALL_API_METERS: {
            meter: MetersResponse(meters[meter]) for meter in meters
        },
        POWERWALL_API_GRID_STATUS: power_wall.grid_status,
    }


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PowerWallEntity(Entity):
    """Base class for powerwall entities."""

    def __init__(self, coordinator, site_info, ip_address):
        """Initialize the sensor."""
        super().__init__()
        self._coordinator = coordinator
        self._site_info = site_info
        self._site_name = site_info[POWERWALL_SITE_NAME]
        self._ip_address = ip_address

    @property
    def device_info(self):
        """Powerwall device info."""
        return {
            "identifiers": {(DOMAIN, self._ip_address)},
            "name": self._site_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
