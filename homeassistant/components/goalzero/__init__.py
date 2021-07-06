"""The Goal Zero Yeti integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from goalzero import Yeti, exceptions

from homeassistant.components.binary_sensor import DOMAIN as DOMAIN_BINARY_SENSOR
from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_FIRMWARE_VERSION,
    ATTR_FOREIGN_ACCESSORY,
    ATTRIBUTION,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [DOMAIN_BINARY_SENSOR, DOMAIN_SENSOR, DOMAIN_SWITCH]


async def async_setup_entry(hass, entry):
    """Set up Goal Zero Yeti from a config entry."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]

    session = async_get_clientsession(hass)
    api = Yeti(host, hass.loop, session)
    try:
        await api.init_connect()
    except exceptions.ConnectError as ex:
        _LOGGER.warning("Failed to connect to device %s", ex)
        raise ConfigEntryNotReady from ex

    async def async_update_data():
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
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
        DATA_KEY_COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class YetiEntity(CoordinatorEntity):
    """Representation of a Goal Zero Yeti entity."""

    def __init__(self, api, coordinator, name, server_unique_id):
        """Initialize a Goal Zero Yeti entity."""
        super().__init__(coordinator)
        self.api = api
        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, server_unique_id)},
            ATTR_MANUFACTURER: "Goal Zero",
            ATTR_NAME: name,
            ATTR_MODEL: self.api.sysdata.get(ATTR_MODEL),
            ATTR_SW_VERSION: self.api.data.get(ATTR_FIRMWARE_VERSION),
        }

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "wifi_ssid": self.api.data.get("ssid"),
            "ip_address": self.api.data.get("ipAddr"),
        }
        if (
            ATTR_FOREIGN_ACCESSORY in self.api.data
            and self.api.data[ATTR_FOREIGN_ACCESSORY] is not None
        ):
            attributes["accessory"] = self.api.data[ATTR_FOREIGN_ACCESSORY][ATTR_MODEL]
            attributes["accessory_firmware"] = self.api.data[ATTR_FOREIGN_ACCESSORY][
                ATTR_FIRMWARE_VERSION
            ]
        return attributes
