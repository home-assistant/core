"""Data update coordinator for the Webmin integration."""
from __future__ import annotations

from typing import Any

from webmin_xmlrpc.client import WebminInstance
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


class WebminUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The Webmin data update coordinator."""

    mac_address: str

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Webmin data update coordinator."""

        super().__init__(
            hass, logger=LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )
        base_url = URL.build(
            scheme="https" if config_entry.options[CONF_SSL] else "http",
            user=config_entry.options[CONF_USERNAME],
            password=config_entry.options[CONF_PASSWORD],
            host=config_entry.options[CONF_HOST],
            port=int(config_entry.options[CONF_PORT]),
        )
        self.instance = WebminInstance(
            session=async_create_clientsession(
                hass,
                verify_ssl=config_entry.options[CONF_VERIFY_SSL],
                base_url=base_url,
            )
        )
        self.device_info = DeviceInfo(
            configuration_url=base_url,
            name=config_entry.options[CONF_HOST],
        )

    async def async_setup(self) -> None:
        """Provide needed data to the device info."""
        ifaces = [iface for iface in self.data["active_interfaces"] if "ether" in iface]
        ifaces.sort(key=lambda x: x["ether"])
        self.mac_address = format_mac(ifaces[0]["ether"])
        self.device_info[ATTR_CONNECTIONS] = {
            (CONNECTION_NETWORK_MAC, format_mac(iface["ether"])) for iface in ifaces
        }
        self.device_info[ATTR_IDENTIFIERS] = {
            (DOMAIN, format_mac(iface["ether"])) for iface in ifaces
        }

    async def _async_update_data(self) -> dict[str, Any]:
        return await self.instance.update()
