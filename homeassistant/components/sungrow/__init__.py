"""The Sungrow Solar Energy integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from urllib.parse import ParseResult, urlparse

from SungrowModbusClient import Client, sungrow_register

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

from .config_flow import CannotConnect
from .const import ALTERNATOR_LOSS, DOMAIN, TOTAL_ACTIVE_POWER, TOTAL_DC_POWER

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sungrow Solar Energy from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = SungrowData(hass, entry)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SungrowData(update_coordinator.DataUpdateCoordinator):
    """Get and update the latest data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data object."""
        super().__init__(
            hass, _LOGGER, name="Sungrow", update_interval=timedelta(seconds=300)
        )

        self.host = entry.data[CONF_HOST]
        self.port = entry.data.get(CONF_PORT, 502)

        self.unique_id = entry.entry_id
        self.name = entry.title

        # Allow user to enter URLs with or without 'http://'
        url = urlparse(self.host, "http")
        # if only path is given we use this as address
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        # reassamble url with http prefix for link in UI
        url = ParseResult("http", netloc, path, *url[3:])
        self.config_url = url.geturl()

        self.client = Client(sungrow_register.regmap, self.host, self.port)

        _LOGGER.debug(
            "Sungrow setting with host: %s",
            self.host,
        )

    def update(self) -> dict:
        """Update register data from device."""
        self.client.load_register()
        return self.client.inverter

    async def _async_update_data(self) -> dict:
        """Update the data from the Sungrow WiNet-S device."""
        try:
            data = await self.hass.async_add_executor_job(self.update)

        except CannotConnect as err:
            _LOGGER.error("No route to host/endpoint: %s", self.host)
            raise update_coordinator.UpdateFailed(err)

        data[ALTERNATOR_LOSS] = data.get(TOTAL_DC_POWER, 0) - data.get(
            TOTAL_ACTIVE_POWER, 0
        )

        return data
