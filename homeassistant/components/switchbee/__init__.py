"""The SwitchBee Smart Home integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import switchbee

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_EXPOSE_GROUP_SWITCHES, CONF_EXPOSE_SCENARIOS, DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBee Smart Home from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    central_unit = entry.data[CONF_HOST]
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    expose_group_switches = entry.data[CONF_EXPOSE_GROUP_SWITCHES]
    expose_scenarios = entry.data[CONF_EXPOSE_SCENARIOS]

    websession = async_get_clientsession(hass, verify_ssl=False)
    api = switchbee.SwitchBeeAPI(central_unit, user, password, websession)
    try:
        await api.login()
    except switchbee.SwitchBeeError as exp:
        raise PlatformNotReady(
            f"Failed to login to the central unit {central_unit} with the user {user}: {exp}"
        ) from switchbee.SwitchBeeError

    coordinator = SwitchBeeCoordinator(
        hass, api, scan_interval, expose_group_switches, expose_scenarios
    )
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

    def __init__(
        self, hass, swb_api, scan_interval, expose_group_switches, expose_scenarios
    ):
        """Initialize."""
        self._api = swb_api
        self._devices = None
        self._mac = ""
        self._reconnect_counts = 0
        self._expose_group_switches = expose_group_switches
        self._expose_scenarios = expose_scenarios
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
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

        # The devices are loaded once
        if self._devices is None:
            # Try to load the devices from the CU for the first time
            try:
                result = await self._api.get_configuration()
            except switchbee.SwitchBeeError as exp:
                raise UpdateFailed(
                    f"Error communicating with API: {exp}"
                ) from switchbee.SwitchBeeError
            else:
                _LOGGER.debug("Loaded devices")
                self._devices = {}
                # re-arrange the devices in a lookup table
                supported_types = [
                    switchbee.TYPE_DIMMER,
                    switchbee.TYPE_SHUTTER,
                    switchbee.TYPE_SWITCH,
                    switchbee.TYPE_TIMED_POWER,
                ]

                if self._expose_group_switches:
                    supported_types.append(switchbee.TYPE_GROUP_SWITCH)
                if self._expose_scenarios:
                    supported_types.append(switchbee.TYPE_SCENARIO)

                self._mac = result[switchbee.ATTR_DATA][switchbee.ATTR_MAC]
                for zone in result[switchbee.ATTR_DATA][switchbee.ATTR_ZONES]:
                    for item in zone[switchbee.ATTR_ITEMS]:
                        if item[switchbee.ATTR_TYPE] in supported_types:
                            item["area"] = zone[
                                "name"
                            ]  # the zone will be used to suggest areas later

                            self._devices[item[switchbee.ATTR_ID]] = item

        # Get the state of the devices
        try:
            result = await self._api.get_multiple_states(list(self._devices.keys()))
        except switchbee.SwitchBeeError as exp:
            _LOGGER.warning(
                "Failed to fetch devices states from the central unit status=%s", exp
            )
            raise UpdateFailed(
                f"Error communicating with API: {exp}"
            ) from switchbee.SwitchBeeError
        else:
            states = result[switchbee.ATTR_DATA]
            for state in states:
                if state[switchbee.ATTR_ID] in self._devices:
                    self._devices[state[switchbee.ATTR_ID]]["state"] = state["state"]
                    self._devices[state[switchbee.ATTR_ID]][
                        "uid"
                    ] = f"{self._mac}-{state[switchbee.ATTR_ID]}"

            return self._devices
