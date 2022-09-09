"""The air-Q integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioairq import AirQ
from aiohttp.client_exceptions import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MANUFACTURER, TARGET_ROUTE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


class AirQCoordinator(DataUpdateCoordinator):
    """Coordinator is responsible for querying the device at a specified route."""

    device_info = DeviceInfo(manufacturer=MANUFACTURER)
    device_id: str = ""

    def __init__(
        self,
        hass: HomeAssistant,
        update_interval: timedelta,
        address: str,
        passw: str,
    ) -> None:
        """Initialise a custom coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        session = async_get_clientsession(hass)
        self.airq = AirQ(address, passw, session)

    async def _async_update_data(self) -> dict:
        """Fetch the data from the device."""
        data = await self.airq.get(TARGET_ROUTE)
        return self.airq.drop_uncertainties_from_data(data)

    async def _async_fetch_device_info(self) -> None:
        """Fetch static config information from the device."""
        try:
            device_info = await self.airq.fetch_device_info()
        except ClientError as err:
            self.last_update_success = False
            self.last_exception = err
            return

        self.device_id = device_info.pop("id")

        self.device_info["suggested_area"] = device_info.pop("room_type")
        self.device_info["identifiers"] = {(DOMAIN, self.device_id)}
        self.device_info.update(device_info)

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        Additionally fetches static device information, which is then used
        to instantiate each AirQSensor.

        Will automatically raise ConfigEntryNotReady if the refresh
        fails. Additionally logging is handled by config entry setup
        to ensure that multiple retries do not cause log spam.
        """
        await self._async_fetch_device_info()
        await super().async_config_entry_first_refresh()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up air-Q from a config entry."""

    coordinator = AirQCoordinator(
        hass,
        update_interval=timedelta(seconds=10),
        address=entry.data[CONF_IP_ADDRESS],
        passw=entry.data[CONF_PASSWORD],
    )

    # Query the device for the first time and initialise coordinator.data
    await coordinator.async_config_entry_first_refresh()

    # Record the coordinator in a global store
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
