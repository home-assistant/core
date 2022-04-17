"""The SwitchBee Smart Home integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import switchbee

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.COVER, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBee Smart Home from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    central_unit = entry.data[CONF_IP_ADDRESS]
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    api = switchbee.SwitchBee(central_unit, user, password)
    coordinator = SwitchBeeCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(update_listener))
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class SwitchBeeCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Freedompro data API."""

    def __init__(self, hass, swb_api):
        """Initialize."""
        self._hass = hass
        self._api = swb_api
        self._devices = None
        self._mac = ""

        update_interval = timedelta(seconds=3)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    @property
    def api(self):
        """Return SwitchBee API object."""
        return self._api

    async def _async_update_data(self):
        if self._devices is None:
            if not await self._api.login():
                raise UpdateFailed()

            result = await self._api.get_configuration()
            if (
                switchbee.ATTR_STATUS not in result
                or result[switchbee.ATTR_STATUS] != switchbee.STATUS_OK
            ):
                raise UpdateFailed()

            self._devices = {}
            self._mac = result[switchbee.ATTR_DATA][switchbee.ATTR_MAC]
            for zone in result[switchbee.ATTR_DATA][switchbee.ATTR_ZONES]:
                for item in zone[switchbee.ATTR_ITEMS]:
                    if item[switchbee.ATTR_TYPE] in switchbee.SUPPORTED_ITEMS:
                        self._devices[item[switchbee.ATTR_ID]] = item

        result = await self._api.get_multiple_states(list(self._devices.keys()))
        if (
            switchbee.ATTR_STATUS not in result
            or result[switchbee.ATTR_STATUS] != switchbee.STATUS_OK
        ):
            raise UpdateFailed()

        result = result[switchbee.ATTR_DATA]
        for device in result:
            if device[switchbee.ATTR_ID] in self._devices:
                self._devices[device[switchbee.ATTR_ID]]["state"] = device["state"]
                self._devices[device[switchbee.ATTR_ID]][
                    "uid"
                ] = f"{self._mac}-{device[switchbee.ATTR_ID]}"

        return self._devices
