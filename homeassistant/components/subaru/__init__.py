"""The Subaru integration."""

from datetime import timedelta
import logging
import time

from subarulink import Controller as SubaruAPI, InvalidCredentials, SubaruException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_UPDATE_ENABLED,
    COORDINATOR_NAME,
    DOMAIN,
    ENTRY_CONTROLLER,
    ENTRY_COORDINATOR,
    ENTRY_VEHICLES,
    FETCH_INTERVAL,
    MANUFACTURER,
    PLATFORMS,
    UPDATE_INTERVAL,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_SERVICE,
    VEHICLE_HAS_REMOTE_START,
    VEHICLE_HAS_SAFETY_SERVICE,
    VEHICLE_LAST_UPDATE,
    VEHICLE_MODEL_NAME,
    VEHICLE_MODEL_YEAR,
    VEHICLE_NAME,
    VEHICLE_VIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Subaru from a config entry."""
    config = entry.data
    websession = aiohttp_client.async_get_clientsession(hass)
    try:
        controller = SubaruAPI(
            websession,
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config[CONF_DEVICE_ID],
            config[CONF_PIN],
            None,
            config[CONF_COUNTRY],
            update_interval=UPDATE_INTERVAL,
            fetch_interval=FETCH_INTERVAL,
        )
        _LOGGER.debug("Using subarulink %s", controller.version)
        await controller.connect()
    except InvalidCredentials:
        _LOGGER.error("Invalid account")
        return False
    except SubaruException as err:
        raise ConfigEntryNotReady(err.message) from err

    vehicle_info = {}
    for vin in controller.get_vehicles():
        if controller.get_subscription_status(vin):
            vehicle_info[vin] = get_vehicle_info(controller, vin)

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await refresh_subaru_data(entry, vehicle_info, controller)
        except SubaruException as err:
            raise UpdateFailed(err.message) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=COORDINATOR_NAME,
        update_method=async_update_data,
        update_interval=timedelta(seconds=FETCH_INTERVAL),
    )

    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_CONTROLLER: controller,
        ENTRY_COORDINATOR: coordinator,
        ENTRY_VEHICLES: vehicle_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def refresh_subaru_data(config_entry, vehicle_info, controller):
    """Refresh local data with data fetched via Subaru API.

    Subaru API calls assume a server side vehicle context
    Data fetch/update must be done for each vehicle
    """
    data = {}

    for vehicle in vehicle_info.values():
        vin = vehicle[VEHICLE_VIN]

        # Optionally send an "update" remote command to vehicle (throttled with update_interval)
        if config_entry.options.get(CONF_UPDATE_ENABLED, False):
            await update_subaru(vehicle, controller)

        # Fetch data from Subaru servers
        await controller.fetch(vin, force=True)

        # Update our local data that will go to entity states
        if received_data := await controller.get_data(vin):
            data[vin] = received_data

    return data


async def update_subaru(vehicle, controller):
    """Commands remote vehicle update (polls the vehicle to update subaru API cache)."""
    cur_time = time.time()
    last_update = vehicle[VEHICLE_LAST_UPDATE]

    if cur_time - last_update > controller.get_update_interval():
        await controller.update(vehicle[VEHICLE_VIN], force=True)
        vehicle[VEHICLE_LAST_UPDATE] = cur_time


def get_vehicle_info(controller, vin):
    """Obtain vehicle identifiers and capabilities."""
    return {
        VEHICLE_VIN: vin,
        VEHICLE_MODEL_NAME: controller.get_model_name(vin),
        VEHICLE_MODEL_YEAR: controller.get_model_year(vin),
        VEHICLE_NAME: controller.vin_to_name(vin),
        VEHICLE_HAS_EV: controller.get_ev_status(vin),
        VEHICLE_API_GEN: controller.get_api_gen(vin),
        VEHICLE_HAS_REMOTE_START: controller.get_res_status(vin),
        VEHICLE_HAS_REMOTE_SERVICE: controller.get_remote_status(vin),
        VEHICLE_HAS_SAFETY_SERVICE: controller.get_safety_status(vin),
        VEHICLE_LAST_UPDATE: 0,
    }


def get_device_info(vehicle_info):
    """Return DeviceInfo object based on vehicle info."""
    return DeviceInfo(
        identifiers={(DOMAIN, vehicle_info[VEHICLE_VIN])},
        manufacturer=MANUFACTURER,
        model=f"{vehicle_info[VEHICLE_MODEL_YEAR]} {vehicle_info[VEHICLE_MODEL_NAME]}",
        name=vehicle_info[VEHICLE_NAME],
    )
