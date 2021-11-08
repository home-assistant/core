"""Data update coordinator for AVM FRITZ!SmartHome devices."""
from __future__ import annotations

from datetime import timedelta

from pyfritzhome import Fritzhome, FritzhomeDevice, LoginError
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CONNECTIONS, DOMAIN, LOGGER


class FritzboxDataUpdateCoordinator(DataUpdateCoordinator):
    """Fritzbox Smarthome device data update coordinator."""

    configuration_url: str

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Fritzbox Smarthome device coordinator."""
        self.entry = entry
        self.fritz: Fritzhome = hass.data[DOMAIN][self.entry.entry_id][CONF_CONNECTIONS]
        self.configuration_url = self.fritz.get_prefixed_host()
        super().__init__(
            hass,
            LOGGER,
            name=entry.entry_id,
            update_interval=timedelta(seconds=30),
        )

    def _update_fritz_devices(self) -> dict[str, FritzhomeDevice]:
        """Update all fritzbox device data."""
        try:
            devices = self.fritz.get_devices()
        except requests.exceptions.ConnectionError as ex:
            raise ConfigEntryNotReady from ex
        except requests.exceptions.HTTPError:
            # If the device rebooted, login again
            try:
                self.fritz.login()
            except LoginError as ex:
                raise ConfigEntryAuthFailed from ex
            devices = self.fritz.get_devices()

        data = {}
        self.fritz.update_devices()
        for device in devices:
            # assume device as unavailable, see #55799
            if (
                device.has_powermeter
                and device.present
                and hasattr(device, "voltage")
                and device.voltage <= 0
                and device.power <= 0
                and device.energy <= 0
            ):
                LOGGER.debug("Assume device %s as unavailable", device.name)
                device.present = False

            data[device.ain] = device
        return data

    async def _async_update_data(self) -> dict[str, FritzhomeDevice]:
        """Fetch all device data."""
        return await self.hass.async_add_executor_job(self._update_fritz_devices)
