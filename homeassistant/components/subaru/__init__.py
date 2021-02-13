"""The Subaru integration."""
import asyncio
from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from subarulink import Controller as SubaruAPI, SubaruException

from .const import (
    CONF_HARD_POLL_INTERVAL,
    COORDINATOR_NAME,
    DEFAULT_HARD_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_CONTROLLER,
    ENTRY_COORDINATOR,
    ENTRY_LISTENER,
    ENTRY_VEHICLES,
    SUPPORTED_PLATFORMS,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_SERVICE,
    VEHICLE_HAS_REMOTE_START,
    VEHICLE_HAS_SAFETY_SERVICE,
    VEHICLE_LAST_UPDATE,
    VEHICLE_NAME,
    VEHICLE_VIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, base_config):
    """Do nothing since this integration does not support configuration.yml setup."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, entry):
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
            update_interval=entry.options.get(
                CONF_HARD_POLL_INTERVAL, DEFAULT_HARD_POLL_INTERVAL
            ),
        )
        await controller.connect()
    except SubaruException as err:
        raise ConfigEntryNotReady(err) from err

    vehicle_info = {}
    for vin in controller.get_vehicles():
        vehicle_info[vin] = get_vehicle_info(controller, vin)

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await subaru_update(vehicle_info, controller)
        except SubaruException as err:
            raise UpdateFailed(err.message) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=COORDINATOR_NAME,
        update_method=async_update_data,
        update_interval=timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )

    await coordinator.async_refresh()

    hass.data.get(DOMAIN)[entry.entry_id] = {
        ENTRY_CONTROLLER: controller,
        ENTRY_COORDINATOR: coordinator,
        ENTRY_VEHICLES: vehicle_info,
        ENTRY_LISTENER: entry.add_update_listener(update_listener),
    }

    for component in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in SUPPORTED_PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][ENTRY_LISTENER]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    controller = data[ENTRY_CONTROLLER]
    coordinator = data[ENTRY_COORDINATOR]

    old_update_interval = controller.get_update_interval()
    old_fetch_interval = coordinator.update_interval

    new_update_interval = config_entry.options.get(
        CONF_HARD_POLL_INTERVAL, DEFAULT_HARD_POLL_INTERVAL
    )
    new_fetch_interval = config_entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )

    if old_update_interval != new_update_interval:
        _LOGGER.debug(
            "Changing update_interval from %s to %s",
            old_update_interval,
            new_update_interval,
        )
        controller.set_update_interval(new_update_interval)

    if old_fetch_interval != new_fetch_interval:
        _LOGGER.debug(
            "Changing fetch_interval from %s to %s",
            old_fetch_interval,
            new_fetch_interval,
        )
        coordinator.update_interval = timedelta(seconds=new_fetch_interval)


async def subaru_update(vehicle_info, controller):
    """
    Update local data from Subaru API.

    Subaru API calls assume a server side vehicle context
    Data fetch/update must be done for each vehicle
    """
    data = {}

    for vehicle in vehicle_info.values():
        vin = vehicle[VEHICLE_VIN]

        # Active subscription required
        if not vehicle[VEHICLE_HAS_SAFETY_SERVICE]:
            continue

        # Poll vehicle (throttled with update_interval)
        await refresh_subaru_data(vehicle, controller)

        # Fetch data from Subaru servers
        await controller.fetch(vin, force=True)

        # Update our local data that will go to entity states
        data[vin] = await controller.get_data(vin)

    return data


async def refresh_subaru_data(vehicle, controller):
    """Commands remote vehicle update (polls the vehicle to update subaru API cache)."""
    cur_time = time.time()
    last_update = vehicle[VEHICLE_LAST_UPDATE]

    if cur_time - last_update > controller.get_update_interval():
        await controller.update(vehicle[VEHICLE_VIN], force=True)
        vehicle[VEHICLE_LAST_UPDATE] = cur_time


def get_vehicle_info(controller, vin):
    """Obtain vehicle identifiers and capabilities."""
    info = {
        VEHICLE_VIN: vin,
        VEHICLE_NAME: controller.vin_to_name(vin),
        VEHICLE_HAS_EV: controller.get_ev_status(vin),
        VEHICLE_API_GEN: controller.get_api_gen(vin),
        VEHICLE_HAS_REMOTE_START: controller.get_res_status(vin),
        VEHICLE_HAS_REMOTE_SERVICE: controller.get_remote_status(vin),
        VEHICLE_HAS_SAFETY_SERVICE: controller.get_safety_status(vin),
        VEHICLE_LAST_UPDATE: 0,
    }
    return info
