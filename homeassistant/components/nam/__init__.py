"""The Nettigo Air Monitor component."""
from __future__ import annotations

import asyncio
import logging
from typing import cast

from aiohttp.client_exceptions import ClientConnectorError, ClientError
from nettigo_air_monitor import (
    ApiError,
    AuthFailedError,
    ConnectionOptions,
    InvalidSensorDataError,
    NAMSensors,
    NettigoAirMonitor,
)

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_SDS011,
    ATTR_SPS30,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nettigo as config entry."""
    host: str = entry.data[CONF_HOST]
    username: str | None = entry.data.get(CONF_USERNAME)
    password: str | None = entry.data.get(CONF_PASSWORD)

    websession = async_get_clientsession(hass)

    options = ConnectionOptions(host=host, username=username, password=password)
    try:
        nam = await NettigoAirMonitor.create(websession, options)
    except (ApiError, ClientError, ClientConnectorError, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady from err

    try:
        await nam.async_check_credentials()
    except ApiError as err:
        raise ConfigEntryNotReady from err
    except AuthFailedError as err:
        raise ConfigEntryAuthFailed from err

    coordinator = NAMDataUpdateCoordinator(hass, nam, entry.unique_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove air_quality entities from registry if they exist
    ent_reg = er.async_get(hass)
    for sensor_type in ("sds", ATTR_SDS011, ATTR_SPS30):
        unique_id = f"{coordinator.unique_id}-{sensor_type}"
        if entity_id := ent_reg.async_get_entity_id(
            AIR_QUALITY_PLATFORM, DOMAIN, unique_id
        ):
            _LOGGER.debug("Removing deprecated air_quality entity %s", entity_id)
            ent_reg.async_remove(entity_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NAMDataUpdateCoordinator(DataUpdateCoordinator[NAMSensors]):
    """Class to manage fetching Nettigo Air Monitor data."""

    def __init__(
        self,
        hass: HomeAssistant,
        nam: NettigoAirMonitor,
        unique_id: str | None,
    ) -> None:
        """Initialize."""
        self._unique_id = unique_id
        self.nam = nam

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )

    async def _async_update_data(self) -> NAMSensors:
        """Update data via library."""
        try:
            async with asyncio.timeout(10):
                data = await self.nam.async_update()
        # We do not need to catch AuthFailed exception here because sensor data is
        # always available without authorization.
        except (ApiError, ClientConnectorError, InvalidSensorDataError) as error:
            raise UpdateFailed(error) from error

        return data

    @property
    def unique_id(self) -> str | None:
        """Return a unique_id."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, cast(str, self._unique_id))},
            name="Nettigo Air Monitor",
            sw_version=self.nam.software_version,
            manufacturer=MANUFACTURER,
            configuration_url=f"http://{self.nam.host}/",
        )
