"""The SwitchBee Smart Home integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import switchbee

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_SEC

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBee Smart Home from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    central_unit = entry.data[CONF_HOST]
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    websession = async_get_clientsession(hass, verify_ssl=False)
    api = switchbee.SwitchBee(central_unit, user, password, websession)
    resp = await api.login()
    if resp[switchbee.ATTR_STATUS] != switchbee.STATUS_OK:
        raise PlatformNotReady(
            f"Failed to login to the central unit {central_unit} with the user {user}: {resp}"
        )

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
        self._api = swb_api
        self._devices = None
        self._mac = ""
        self._reconnect_counts = 0
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SEC),
        )

    @property
    def api(self):
        """Return SwitchBee API object."""
        return self._api

    async def _async_update_data(self):
        if self._reconnect_counts != self._api.reconnect_count:
            self._reconnect_counts = self._api.reconnect_count
            _LOGGER.debug(
                "Central Unit re-connected again due to invalid token, total %i",
                self._reconnect_counts,
            )

        if self._devices is None:
            result = await self._api.get_configuration()
            _LOGGER.debug("Loaded devices")
            if (
                switchbee.ATTR_STATUS not in result
                or result[switchbee.ATTR_STATUS] != switchbee.STATUS_OK
            ):
                _LOGGER.warning(
                    "Failed to fetch configuration from the central unit status=%s",
                    result[switchbee.ATTR_STATUS],
                )
                raise UpdateFailed(f"Error communicating with API: {result}")

            self._devices = {}
            self._mac = result[switchbee.ATTR_DATA][switchbee.ATTR_MAC]
            for zone in result[switchbee.ATTR_DATA][switchbee.ATTR_ZONES]:
                for item in zone[switchbee.ATTR_ITEMS]:
                    if item[switchbee.ATTR_TYPE] in [
                        switchbee.TYPE_DIMMER,
                        switchbee.TYPE_SWITCH,
                        switchbee.TYPE_SHUTTER,
                        switchbee.TYPE_OUTLET,
                    ]:
                        self._devices[item[switchbee.ATTR_ID]] = item

        if self._devices is None:
            raise UpdateFailed("Failed to fetch devices")

        result = await self._api.get_multiple_states(list(self._devices.keys()))
        if (
            switchbee.ATTR_STATUS not in result
            or result[switchbee.ATTR_STATUS] != switchbee.STATUS_OK
        ):
            _LOGGER.warning(
                "Failed to fetch devices states from the central unit status=%s", result
            )
            raise UpdateFailed(f"Error communicating with API: {result}")

        states = result[switchbee.ATTR_DATA]
        for state in states:
            if state[switchbee.ATTR_ID] in self._devices:
                self._devices[state[switchbee.ATTR_ID]]["state"] = state["state"]
                self._devices[state[switchbee.ATTR_ID]][
                    "uid"
                ] = f"{self._mac}-{state[switchbee.ATTR_ID]}"

        return self._devices
