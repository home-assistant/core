"""The Airthings integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from airthings import Airthings, AirthingsDevice, AirthingsError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=6)

type AirthingsDataCoordinatorType = DataUpdateCoordinator[dict[str, AirthingsDevice]]
type AirthingsConfigEntry = ConfigEntry[AirthingsDataCoordinatorType]


async def async_setup_entry(hass: HomeAssistant, entry: AirthingsConfigEntry) -> bool:
    """Set up Airthings from a config entry."""
    airthings = Airthings(
        entry.data[CONF_ID],
        entry.data[CONF_SECRET],
        async_get_clientsession(hass),
    )

    async def _update_method() -> dict[str, AirthingsDevice]:
        """Get the latest data from Airthings."""
        try:
            return await airthings.update_devices()  # type: ignore[no-any-return]
        except AirthingsError as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_update_method,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirthingsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
