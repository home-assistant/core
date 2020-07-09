"""The NIU integration."""
import asyncio

from niu import NiuCloud  # , NiuAPIException
import voluptuous as vol
import logging

from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.discovery import load_platform

# from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    NIU_COMPONENTS,
)

_LOGGER = logging.getLogger(__name__)

ENTRY_DEVICES = "devices"
ENTRY_CONTROLLER = "controller"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["sensor"]


def setup(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up NIU from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    conf = entry.get(DOMAIN)

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    # scan_interval = conf[CONF_SCAN_INTERVAL]
    controller = NiuCloud(username=username, password=password)

    conf[ENTRY_CONTROLLER] = controller
    try:
        controller.connect()
    except Exception as ex:
        print(ex)
        return False

    if ENTRY_DEVICES in conf:
        devices = conf[ENTRY_DEVICES]
    elif DOMAIN in entry:

        vehicles = controller.get_vehicles()

        devices = []
        for vehicle in vehicles:
            devices.append(vehicle)

    else:
        devices = []

    if not devices:
        return True

    # for device in devices:
    #    # print(entry)
    #    load_platform(hass, "sensor", DOMAIN, {}, entry)

    controller = setup_entry(hass, entry[DOMAIN])
    hass.data[DOMAIN] = {"controller": controller, "devices": []}

    devices = controller.get_vehicles()
    for device in devices:
        hass.data[DOMAIN]["devices"].append(device)

    for component in NIU_COMPONENTS:
        load_platform(hass, component, DOMAIN, {}, entry)

    return True


def setup_entry(hass, conf: dict):
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    account = NiuCloud(username=username, password=password)

    def update_data():
        try:
            account.update_vehicles()
        except Exception as err:
            _LOGGER.error(f"Error communicating with NIU Cloud: {err}")
            # raise UpdateFailed(f"Error communicating with NIU Cloud: {err}")

    try:
        account.connect()
    except Exception as err:
        _LOGGER.error(f"Error coinnecting to NIU Cloud: {err}")
        return False

    # Is there a sync way to do this?
    # coordinator = DataUpdateCoordinator(
    #    hass,
    #    _LOGGER,
    #    name="niu",
    #    update_method=update_data,
    #    update_interval=CONF_SCAN_INTERVAL,
    # )
    # coordinator.refresh

    update_data()

    return account


class NiuDevice(Entity):
    def __init__(self, niu_device, controller):
        self.niu_device = niu_device
        self.controller = controller

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.niu_device.get_serial()

    @property
    def name(self):
        return self.niu_device.get_name()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_BATTERY_LEVEL: self.niu_device.get_soc(),
            ATTR_BATTERY_CHARGING: self.niu_device.is_charging(),
        }

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": (DOMAIN, self.unique_id),
            "name": self.name,
            "manufacturer": "NIU",
            "model": self.niu_device.get_model(),
        }

    async def async_added_to_hass(self):
        """Register state update callback."""

    async def async_will_remove_from_hass(self):
        """Prepare for unload."""

    def update(self):
        self.controller.update_vehicles()
