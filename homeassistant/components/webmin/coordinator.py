"""Data update coordinator for the Webmin integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS, ATTR_IDENTIFIERS, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER
from .helpers import get_instance_from_options, get_sorted_mac_addresses


class WebminUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The Webmin data update coordinator."""

    config_entry: ConfigEntry
    mac_address: str
    unique_id: str

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Webmin data update coordinator."""

        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        self.instance, base_url = get_instance_from_options(hass, config_entry.options)

        self.device_info = DeviceInfo(
            configuration_url=base_url,
            name=config_entry.options[CONF_HOST],
        )

    async def async_setup(self) -> None:
        """Provide needed data to the device info."""
        mac_addresses = get_sorted_mac_addresses(self.data)
        if len(mac_addresses) > 0:
            self.mac_address = mac_addresses[0]
            self.unique_id = self.mac_address
            self.device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, format_mac(mac_address))
                for mac_address in mac_addresses
            }
            self.device_info[ATTR_IDENTIFIERS] = {
                (DOMAIN, format_mac(mac_address)) for mac_address in mac_addresses
            }
        else:
            self.unique_id = self.config_entry.entry_id

    async def _async_update_data(self) -> dict[str, Any]:
        data = await self.instance.update()
        data["disk_fs"] = {item["dir"]: item for item in data["disk_fs"]}
        return data
