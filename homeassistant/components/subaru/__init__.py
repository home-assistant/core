"""The Subaru integration."""
import asyncio
from datetime import datetime, timedelta
import logging
import time

import async_timeout
from subarulink import Controller as SubaruAPI, SubaruException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import (
    CONF_HARD_POLL_INTERVAL,
    DEFAULT_HARD_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ICONS,
    SUPPORTED_PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, base_config):
    """Set up of Subaru component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Subaru from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    config = entry.data
    websession = aiohttp_client.async_get_clientsession(hass)
    date = datetime.now().strftime("%Y-%m-%d")
    device_name = "Home Assistant: Added " + date
    try:
        controller = SubaruAPI(
            websession,
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config[CONF_DEVICE_ID],
            config[CONF_PIN],
            device_name,
            update_interval=entry.options.get(
                CONF_HARD_POLL_INTERVAL, DEFAULT_HARD_POLL_INTERVAL
            ),
            fetch_interval=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        if not await controller.connect():
            _LOGGER.error("Failed to connect")
            return False
    except SubaruException as ex:
        _LOGGER.error("Unable to communicate with Subaru API: %s", ex.message)
        return False

    vehicle_info = {}
    for vin in controller.get_vehicles():
        vehicle_info[vin] = get_vehicle_info(controller, vin)

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(30):
                data = await subaru_update(vehicle_info, controller)
            return data
        except SubaruException as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="subaru_data",
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
    )

    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "controller": controller,
        "coordinator": coordinator,
        "vehicles": vehicle_info,
        "listener": [entry.add_update_listener(update_listener)],
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
        hass.data[DOMAIN].pop(entry.entry_id)
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)

    return unload_ok


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    controller = hass.data[DOMAIN][config_entry.entry_id]["controller"]
    controller.set_update_interval(config_entry.options.get(CONF_HARD_POLL_INTERVAL))
    controller.set_fetch_interval(config_entry.options.get(CONF_SCAN_INTERVAL))


class SubaruEntity(Entity):
    """Representation of a Subaru Device."""

    def __init__(self, vehicle_info, coordinator):
        """Initialize the Subaru Device."""
        self.coordinator = coordinator
        self.car_name = vehicle_info["display_name"]
        self.vin = vehicle_info["vin"]
        self._attributes = {}
        self._should_poll = False
        self.title = "entity"

    @property
    def name(self):
        """Return name."""
        return f"{self.car_name} {self.title}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return slugify(
            "Subaru Model {} {} {}".format(
                str(self.vin[3]).upper(), self.vin[-6:], self.title
            )
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(self.title)

    @property
    def should_poll(self):
        """Return the polling state."""
        return self._should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attributes

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": self.car_name,
            "manufacturer": "Subaru",
        }

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_will_remove_from_hass(self):
        """Prepare for unload."""

    async def async_update(self):
        """Update the state of the device."""
        await self.coordinator.async_request_refresh()


async def subaru_update(vehicle_info, controller):
    """
    Fetch or Update data, depending on how long it has been.

    Subaru API calls assume a server side vehicle context
    Data fetch/update must be done for each vehicle
    """
    data = {}

    for vin in vehicle_info.keys():
        # Only g2 api vehicles have data updates
        if vehicle_info[vin]["api_gen"] == "g2":
            cur_time = time.time()
            last_update = vehicle_info[vin]["last_update"]
            last_fetch = vehicle_info[vin]["last_fetch"]

            if cur_time - last_update > controller.get_update_interval():
                if last_update == 0:
                    # Don't do full update on first run so hass setup completes faster
                    await controller.fetch(vin, force=True)
                else:
                    # Invokes Subaru API to perform remote vehicle update
                    await controller.update(vin, force=True)
                    await controller.fetch(vin, force=True)
                vehicle_info[vin]["last_update"] = cur_time
                vehicle_info[vin]["last_fetch"] = cur_time

            elif cur_time - last_fetch > controller.get_fetch_interval():
                # Invokes Subaru API to to fetch remote cached data to local cache
                await controller.fetch(vin, force=True)
                vehicle_info[vin]["last_fetch"] = cur_time

            # Gets subarulink locally cached data
            data[vin] = await controller.get_data(vin)

    return data


def get_vehicle_info(controller, vin):
    """Obtain vehicle identifiers and capabilities."""
    info = {}
    info["vin"] = vin
    info["display_name"] = controller.vin_to_name(vin)
    info["is_ev"] = controller.get_ev_status(vin)
    info["api_gen"] = controller.get_api_gen(vin)
    info["has_res"] = controller.get_res_status(vin)
    info["has_remote"] = controller.get_remote_status(vin)
    info["has_safety"] = controller.get_safety_status(vin)
    info["last_update"] = 0
    info["last_fetch"] = 0
    return info
