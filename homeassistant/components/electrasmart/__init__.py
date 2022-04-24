"""The Electra Air Conditioner integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import electra

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_IMEI, DOMAIN, SCAN_INTERVAL_SEC

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Electra Air Conditioner from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    imei = entry.data[CONF_IMEI]
    token = entry.data[CONF_TOKEN]

    websession = async_get_clientsession(hass)
    electra_api = electra.ElectraAPI(websession, imei, token)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_SEC)

    coordinator = ElectraSmartCoordinator(hass, electra_api, scan_interval)
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


class ElectraSmartCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Electra AC data API."""

    def __init__(self, hass, electra_api, scan_interval):
        """Initialize."""
        self._hass = hass
        self._api = electra_api
        self._devices = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def api(self):
        """Return Electra API object."""
        return self._api

    async def _async_update_data(self):

        if self._devices is None:
            _LOGGER.debug("Fetching Electra AC devices")
            self._devices = {}
            try:
                resp = await self._api.get_devices()
            except electra.ElectraApiError as exp:
                raise UpdateFailed(
                    f"Error communicating with API: {exp}"
                ) from electra.ElectraApiError

            for device in resp:
                self._devices[device.mac] = device

            _LOGGER.debug(
                "%s Electra AC devices were loaded", len(self._devices.items())
            )
        for device_mac in self._devices:
            try:
                await self._api.get_last_telemtry(self._devices[device_mac])
                _LOGGER.debug(
                    "%s (%s) state updated: %s",
                    device_mac,
                    self._devices[device_mac].name,
                    self._devices[device_mac].__dict__,
                )
            except electra.ElectraApiError as exp:
                raise UpdateFailed(
                    f"Failed to get {self._devices[device_mac].name} state: {exp}"
                ) from electra.ElectraApiError

        return self._devices
