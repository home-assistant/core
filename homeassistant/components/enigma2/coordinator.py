"""Data update coordinator for the Enigma2 integration."""

import logging

from openwebif.api import OpenWebIfDevice, OpenWebIfStatus
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

from .const import CONF_SOURCE_BOUQUET, DOMAIN

LOGGER = logging.getLogger(__package__)

type Enigma2ConfigEntry = ConfigEntry[Enigma2UpdateCoordinator]


class Enigma2UpdateCoordinator(DataUpdateCoordinator[OpenWebIfStatus]):
    """The Enigma2 data update coordinator."""

    config_entry: Enigma2ConfigEntry
    device: OpenWebIfDevice
    unique_id: str | None

    def __init__(self, hass: HomeAssistant, config_entry: Enigma2ConfigEntry) -> None:
        """Initialize the Enigma2 data update coordinator."""

        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        base_url = URL.build(
            scheme="http" if not config_entry.data[CONF_SSL] else "https",
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            user=config_entry.data.get(CONF_USERNAME),
            password=config_entry.data.get(CONF_PASSWORD),
        )

        session = async_create_clientsession(
            hass, verify_ssl=config_entry.data[CONF_VERIFY_SSL], base_url=base_url
        )

        self.device = OpenWebIfDevice(
            session, source_bouquet=config_entry.options.get(CONF_SOURCE_BOUQUET)
        )

        self.device_info = DeviceInfo(
            configuration_url=base_url,
            name=config_entry.data[CONF_HOST],
        )

        # set the unique ID for the entities to the config entry unique ID
        # for devices that don't report a MAC address
        self.unique_id = config_entry.unique_id

    async def _async_setup(self) -> None:
        """Provide needed data to the device info."""

        about = await self.device.get_about()
        self.device.mac_address = about["info"]["ifaces"][0]["mac"]
        self.device_info["model"] = about["info"]["model"]
        self.device_info["manufacturer"] = about["info"]["brand"]
        if self.device.mac_address is not None:
            self.device_info[ATTR_IDENTIFIERS] = {
                (DOMAIN, format_mac(iface["mac"]))
                for iface in about["info"]["ifaces"]
                if "mac" in iface and iface["mac"] is not None
            }
            self.device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, format_mac(iface["mac"]))
                for iface in about["info"]["ifaces"]
                if "mac" in iface and iface["mac"] is not None
            }
            self.unique_id = self.device.mac_address
        elif self.unique_id is not None:
            self.device_info[ATTR_IDENTIFIERS] = {(DOMAIN, self.unique_id)}

    async def _async_update_data(self) -> OpenWebIfStatus:
        await self.device.update()
        return self.device.status
