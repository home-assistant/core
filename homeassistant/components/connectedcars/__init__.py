"""The ConnectedCars.io integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from connectedcars import ConnectedCarsClient, ConnectedCarsException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_API_USER_EMAIL,
    ATTR_API_USER_FIRSTNAME,
    ATTR_API_USER_LASTNAME,
    ATTR_API_VEHICLE_FUELLEVEL,
    ATTR_API_VEHICLE_FUELPERCENTAGE,
    ATTR_API_VEHICLE_ID,
    ATTR_API_VEHICLE_LICENSEPLATE,
    ATTR_API_VEHICLE_MAKE,
    ATTR_API_VEHICLE_MODEL,
    ATTR_API_VEHICLE_NAME,
    ATTR_API_VEHICLE_ODOMETER,
    ATTR_API_VEHICLE_POS_LATITUDE,
    ATTR_API_VEHICLE_POS_LONGITUDE,
    ATTR_API_VEHICLE_VIN,
    ATTR_API_VEHICLE_VOLTAGE,
    COMPLETE_QUERY,
    CONF_NAMESPACE,
    CONNECTED_CARS_CLIENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "device_tracker"]
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
UPDATE_INTERVAL = timedelta(minutes=5)  # TODO: Create a config for this


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the ConnectedCars.io component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up ConnectedCars.io from a config entry."""

    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    namespace = config_entry.data[CONF_NAMESPACE]
    ccah = ConnectedCarsClient(username, password, namespace)

    coordinator = ConnectedCarsDataUpdateCoordinator(hass, ccah, UPDATE_INTERVAL)
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


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class ConnectedCarsDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Connected Cars data."""

    def __init__(self, hass, ccah: ConnectedCarsClient, update_interval):
        """Initialize."""
        self.ccah = ccah
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        """Update data via library."""
        with async_timeout.timeout(20):
            try:
                response = await self.ccah.async_query(COMPLETE_QUERY)
            except ConnectedCarsException as error:
                raise UpdateFailed(error)

        data = response["data"]
        viewer = data["viewer"]
        vehicles = viewer["vehicles"]
        vehicle = vehicles[0]["vehicle"]

        flattened_data = {
            ATTR_API_USER_FIRSTNAME: viewer["firstname"],
            ATTR_API_USER_LASTNAME: viewer["lastname"],
            ATTR_API_USER_EMAIL: viewer["email"],
            ATTR_API_VEHICLE_ID: vehicle["id"],
            ATTR_API_VEHICLE_VIN: vehicle["vin"],
            ATTR_API_VEHICLE_MAKE: vehicle["make"],
            ATTR_API_VEHICLE_MODEL: vehicle["model"],
            ATTR_API_VEHICLE_NAME: vehicle["name"],
            ATTR_API_VEHICLE_LICENSEPLATE: vehicle["licensePlate"],
            ATTR_API_VEHICLE_FUELLEVEL: vehicle["fuelLevel"]["liter"],
            ATTR_API_VEHICLE_FUELPERCENTAGE: vehicle["fuelPercentage"]["percent"],
            ATTR_API_VEHICLE_ODOMETER: vehicle["odometer"]["odometer"],
            ATTR_API_VEHICLE_VOLTAGE: vehicle["latestBatteryVoltage"]["voltage"],
            ATTR_API_VEHICLE_POS_LATITUDE: vehicle["position"]["latitude"],
            ATTR_API_VEHICLE_POS_LONGITUDE: vehicle["position"]["longitude"],
        }

        return flattened_data
