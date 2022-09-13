"""The SwitchBee Smart Home integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from switchbee.api import CentralUnitAPI, SwitchBeeError
from switchbee.device import DeviceType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DEFUALT_ALLOWED,
    CONF_DEVICES,
    CONF_SWITCHES_AS_LIGHTS,
    DOMAIN,
    SCAN_INTERVAL_SEC,
)

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBee Smart Home from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    central_unit = entry.data[CONF_HOST]
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    devices_map: dict[str, DeviceType] = {s.display: s for s in DeviceType}
    allowed_devices = [
        devices_map[device]
        for device in entry.options.get(CONF_DEVICES, CONF_DEFUALT_ALLOWED)
    ]
    websession = async_get_clientsession(hass, verify_ssl=False)
    api = CentralUnitAPI(central_unit, user, password, websession)
    try:
        await api.connect()
    except SwitchBeeError:
        return False

    coordinator = SwitchBeeCoordinator(
        hass,
        api,
        SCAN_INTERVAL_SEC,
        allowed_devices,
        entry.data[CONF_SWITCHES_AS_LIGHTS],
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
        self,
        hass,
        swb_api,
        scan_interval,
        devices: list[DeviceType],
        switch_as_light: bool,
    ):
        """Initialize."""
        self._api: CentralUnitAPI = swb_api
        self._reconnect_counts: int = 0
        self._devices_to_include: list[DeviceType] = devices
        self._prev_devices_to_include_to_include: list[DeviceType] = []
        self._mac_addr_fmt: str = format_mac(swb_api.mac)
        self._switch_as_light = switch_as_light
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def api(self) -> CentralUnitAPI:
        """Return SwitchBee API object."""
        return self._api

    @property
    def mac_formated(self) -> str:
        """Return formatted MAC address."""
        return self._mac_addr_fmt

    @property
    def switch_as_light(self) -> bool:
        """Return switch_as_ligh config."""
        return self._switch_as_light

    async def _async_update_data(self):

        if self._reconnect_counts != self._api.reconnect_count:
            self._reconnect_counts = self._api.reconnect_count
            _LOGGER.debug(
                "Central Unit re-connected again due to invalid token, total %i",
                self._reconnect_counts,
            )

        config_changed = False

        if set(self._prev_devices_to_include_to_include) != set(
            self._devices_to_include
        ):
            self._prev_devices_to_include_to_include = self._devices_to_include
            config_changed = True

        # The devices are loaded once during the config_entry
        if not self._api.devices or config_changed:
            # Try to load the devices from the CU for the first time
            try:
                await self._api.fetch_configuration(self._devices_to_include)
            except SwitchBeeError as exp:
                raise UpdateFailed(
                    f"Error communicating with API: {exp}"
                ) from SwitchBeeError
            else:
                _LOGGER.debug("Loaded devices")

        # Get the state of the devices
        try:
            await self._api.fetch_states()
        except SwitchBeeError as exp:
            raise UpdateFailed(
                f"Error communicating with API: {exp}"
            ) from SwitchBeeError
        else:
            return self._api.devices
