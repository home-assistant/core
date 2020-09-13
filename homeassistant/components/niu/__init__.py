"""The NIU integration."""
import asyncio
from collections import defaultdict
from datetime import timedelta
import logging

from niu import NiuAPIException, NiuCloud, NiuNetException, NiuServerException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)


from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_utc_time_change
import homeassistant.util.dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL, NIU_COMPONENTS

_LOGGER = logging.getLogger(__name__)

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


async def async_setup(hass: HomeAssistant, entry: ConfigEntry):
    """Set up NIU component."""

    hass.data.setdefault(DOMAIN, {})
    return True

    # config = entry.get(DOMAIN)
    # if not config:
    #    return True

    # username = config[CONF_USERNAME]
    # password = config[CONF_PASSWORD]
    # token = config[CONF_TOKEN]
    # scan_interval = config[CONF_SCAN_INTERVAL]

    # if username in {entry.title for entry in hass.config_entries.async_entries(DOMAIN)}:
    #    try:
    #        account = NiuCloud(username=username, password=password, token=token)
    #        await account.connect()
    #    except (NiuAPIException, NiuNetException, NiuServerException) as err:
    #        _LOGGER.error("Error connecting to NIU Cloud")
    #        _LOGGER.exception(err)
    #        return False

    # hass.data[DOMAIN] = account

    # for component in NIU_COMPONENTS:
    #    load_platform(hass, component, DOMAIN, {}, entry)

    # return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up NIU as config entry."""

    email = entry.title
    config = entry.data

    # if email in hass.data[DOMAIN] and CONF_SCAN_INTERVAL in hass.data[DOMAIN][email]:
    #    scan_interval = hass.data[DOMAIN][email][CONF_SCAN_INTERVAL]

    username = entry.title
    token = config[CONF_TOKEN]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    try:
        account = NiuCloud(username=username, token=token)
        token = await account.connect()

    except NiuAPIException as ex:
        _LOGGER.error("NIU API Error: %s", ex)
        return False

    async def async_update_data():
        """Fetch data from NIU."""
        print("async update data")
        await account.update_vehicles()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="NIU Update",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "account": account,
    }

    # TODO: Uncomment this
    # hass.config_entries.async_update_entry(
    #    config_entry, data={**config, CONF_TOKEN: token}
    # )

    for component in NIU_COMPONENTS:
        _LOGGER.debug("Loading %s", component)

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def _async_update_listener(hass, entry):
    print("UPDATE LISTENER")
    await hass.config_entries.async_reload(entry.entry_id)


#    """Update when config_entry options update."""
#
#    account = hass.data[DOMAIN][entry.entry_id]["account"]
#    old_update_interval = account.update_interval
#    account.update_interval = entry.options.get(CONF_SCAN_INTERVAL)
#    _LOGGER.debug(
#        "Changing scan_interval from %s to %s",
#        old_update_interval,
#        account.update_interval,
#    )


# async def setup_account(hass, conf: dict):
#    """Set up a NIU account."""
#    username = conf[CONF_USERNAME]
#    password = conf[CONF_PASSWORD]
#    token = conf[CONF_TOKEN]
#    account = NiuCloud(username=username, password=password, token=token)
#
#    try:
#        await account.connect()
#    except (NiuAPIException, NiuNetException, NiuServerException) as err:
#        _LOGGER.error("Error connecting to NIU Cloud")
#        _LOGGER.exception(err)
#        return False
#
#    now = dt_util.utcnow()
#    track_utc_time_change(
#        hass,
#        account.update,
#        minute=range(
#            now.minute % conf[CONF_SCAN_INTERVAL], 60, conf[CONF_SCAN_INTERVAL]
#        ),
#        second=now.second,
#    )
#
#    return account


class NiuVehicle(CoordinatorEntity, Entity):
    """Represents a NIU vehicle."""

    def __init__(self, niu, vehicle, coordinator):
        """Initialize the class."""
        super().__init__(coordinator)
        self.niu = niu
        self.vehicle = vehicle
        self.coordinator = coordinator

    @property
    def name(self):
        """Return the vehicle's name"""
        return self.vehicle.name

    @property
    def unique_id(self):
        """Return the vehicle's unique id"""

        return self.vehicle.serial_number

    # @property
    # def should_poll(self):
    #    """Returns the polling state."""
    #    return False

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "NIU",
            "model": self.vehicle.model,
            "sw_version": self.vehicle.firmware_version,
        }

    def update(self, **kwargs):
        """Get updates from NIU"""
        print("update vehicles")
        self.niu.update_vehicles()

    # async def async_update(self):
    #    """Update the entity.

    #    Only used by the generic entity update service.
    #    """
    #    print("ASYNC UPDATE")
    #    await self.coordinator.async_request_refresh()

    # async def async_added_to_hass(self):
    #    """When entity is added to hass."""
    #    self.async_on_remove(
    #        self.coordinator.async_add_listener(self.async_write_ha_state)
    #    )

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_BATTERY_LEVEL: self.vehicle.soc(),
            ATTR_BATTERY_CHARGING: self.vehicle.is_charging,
        }

