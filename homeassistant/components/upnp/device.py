"""Home Assistant representation of an UPnP/IGD."""
import asyncio
from ipaddress import IPv4Address
from typing import List, Mapping

from async_upnp_client import UpnpFactory
from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.profiles.igd import IgdDevice

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.dt as dt_util

from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    CONF_LOCAL_IP,
    DISCOVERY_LOCATION,
    DISCOVERY_ST,
    DISCOVERY_UDN,
    DISCOVERY_USN,
    DOMAIN,
    DOMAIN_CONFIG,
    LOGGER as _LOGGER,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    TIMESTAMP,
)


class Device:
    """Home Assistant representation of an UPnP/IGD."""

    def __init__(self, igd_device):
        """Initialize UPnP/IGD device."""
        self._igd_device: IgdDevice = igd_device
        self._mapped_ports = []

    @classmethod
    async def async_discover(cls, hass: HomeAssistantType) -> List[Mapping]:
        """Discover UPnP/IGD devices."""
        _LOGGER.debug("Discovering UPnP/IGD devices")
        local_ip = None
        if DOMAIN in hass.data and DOMAIN_CONFIG in hass.data[DOMAIN]:
            local_ip = hass.data[DOMAIN][DOMAIN_CONFIG].get(CONF_LOCAL_IP)
        if local_ip:
            local_ip = IPv4Address(local_ip)

        discovery_infos = await IgdDevice.async_search(source_ip=local_ip, timeout=10)

        # add extra info and store devices
        devices = []
        for discovery_info in discovery_infos:
            discovery_info[DISCOVERY_UDN] = discovery_info["_udn"]
            discovery_info[DISCOVERY_ST] = discovery_info["st"]
            discovery_info[DISCOVERY_LOCATION] = discovery_info["location"]
            usn = f"{discovery_info[DISCOVERY_UDN]}::{discovery_info[DISCOVERY_ST]}"
            discovery_info[DISCOVERY_USN] = usn
            _LOGGER.debug("Discovered device: %s", discovery_info)

            devices.append(discovery_info)

        return devices

    @classmethod
    async def async_create_device(cls, hass: HomeAssistantType, ssdp_location: str):
        """Create UPnP/IGD device."""
        # build async_upnp_client requester
        session = async_get_clientsession(hass)
        requester = AiohttpSessionRequester(session, True, 10)

        # create async_upnp_client device
        factory = UpnpFactory(requester, disable_state_variable_validation=True)
        upnp_device = await factory.async_create_device(ssdp_location)

        igd_device = IgdDevice(upnp_device, None)

        return cls(igd_device)

    @property
    def udn(self) -> str:
        """Get the UDN."""
        return self._igd_device.udn

    @property
    def name(self) -> str:
        """Get the name."""
        return self._igd_device.name

    @property
    def manufacturer(self) -> str:
        """Get the manufacturer."""
        return self._igd_device.manufacturer

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._igd_device.model_name

    @property
    def device_type(self) -> str:
        """Get the device type."""
        return self._igd_device.device_type

    @property
    def unique_id(self) -> str:
        """Get the unique id."""
        return f"{self.udn}::{self.device_type}"

    def __str__(self) -> str:
        """Get string representation."""
        return f"IGD Device: {self.name}/{self.udn}::{self.device_type}"

    async def async_get_traffic_data(self) -> Mapping[str, any]:
        """
        Get all traffic data in one go.

        Traffic data consists of:
        - total bytes sent
        - total bytes received
        - total packets sent
        - total packats received

        Data is timestamped.
        """
        _LOGGER.debug("Getting traffic statistics from device: %s", self)

        values = await asyncio.gather(
            self._igd_device.async_get_total_bytes_received(),
            self._igd_device.async_get_total_bytes_sent(),
            self._igd_device.async_get_total_packets_received(),
            self._igd_device.async_get_total_packets_sent(),
        )

        return {
            TIMESTAMP: dt_util.utcnow(),
            BYTES_RECEIVED: values[0],
            BYTES_SENT: values[1],
            PACKETS_RECEIVED: values[2],
            PACKETS_SENT: values[3],
        }
