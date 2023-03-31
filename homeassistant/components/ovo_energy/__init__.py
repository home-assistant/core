"""Support for OVO Energy."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

import aiohttp
import async_timeout
from ovoenergy import OVODailyUsage
from ovoenergy.ovoenergy import OVOEnergy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_ACCOUNT, DATA_CLIENT, DATA_COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OVO Energy from a config entry."""

    client = OVOEnergy()

    try:
        authenticated = await client.authenticate(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_ACCOUNT],
        )
    except aiohttp.ClientError as exception:
        _LOGGER.warning(exception)
        raise ConfigEntryNotReady from exception

    if not authenticated:
        raise ConfigEntryAuthFailed

    async def async_update_data() -> OVODailyUsage:
        """Fetch data from OVO Energy."""
        async with async_timeout.timeout(10):
            try:
                authenticated = await client.authenticate(
                    entry.data[CONF_USERNAME],
                    entry.data[CONF_PASSWORD],
                    entry.data[CONF_ACCOUNT],
                )
            except aiohttp.ClientError as exception:
                raise UpdateFailed(exception) from exception
            if not authenticated:
                raise ConfigEntryAuthFailed("Not authenticated with OVO Energy")
            return await client.get_daily_usage(datetime.utcnow().strftime("%Y-%m"))

    coordinator = DataUpdateCoordinator[OVODailyUsage](
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=3600),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Setup components
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OVO Energy config entry."""
    # Unload sensors
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    del hass.data[DOMAIN][entry.entry_id]

    return unload_ok


class OVOEnergyEntity(CoordinatorEntity[DataUpdateCoordinator[OVODailyUsage]]):
    """Defines a base OVO Energy entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[OVODailyUsage],
        client: OVOEnergy,
    ) -> None:
        """Initialize the OVO Energy entity."""
        super().__init__(coordinator)
        self._client = client


class OVOEnergyDeviceEntity(OVOEnergyEntity):
    """Defines a OVO Energy device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this OVO Energy instance."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._client.account_id)},
            manufacturer="OVO Energy",
            name=self._client.username,
        )
