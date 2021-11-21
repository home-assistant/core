"""The Goal Zero Yeti integration."""
from __future__ import annotations

import logging

from goalzero import Yeti, exceptions

from homeassistant.components.binary_sensor import DOMAIN as DOMAIN_BINARY_SENSOR
from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_MODEL, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTRIBUTION,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DOMAIN,
    MANUFACTURER,
    MIN_TIME_BETWEEN_UPDATES,
)

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [DOMAIN_BINARY_SENSOR, DOMAIN_SENSOR, DOMAIN_SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Goal Zero Yeti from a config entry."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]

    api = Yeti(host, async_get_clientsession(hass))
    try:
        await api.init_connect()
    except exceptions.ConnectError as ex:
        raise ConfigEntryNotReady(f"Failed to connect to device: {ex}") from ex

    async def async_update_data() -> None:
        """Fetch data from API endpoint."""
        try:
            await api.get_state()
        except exceptions.ConnectError as err:
            raise UpdateFailed("Failed to communicate with device") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
        DATA_KEY_COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class YetiEntity(CoordinatorEntity):
    """Representation of a Goal Zero Yeti entity."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(
        self,
        api: Yeti,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
    ) -> None:
        """Initialize a Goal Zero Yeti entity."""
        super().__init__(coordinator)
        self.api = api
        self._name = name
        self._server_unique_id = server_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.api.sysdata["macAddress"])},
            identifiers={(DOMAIN, self._server_unique_id)},
            manufacturer=MANUFACTURER,
            model=self.api.sysdata[ATTR_MODEL],
            name=self._name,
            sw_version=self.api.data["firmwareVersion"],
        )
