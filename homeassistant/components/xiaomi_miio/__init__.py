"""Support for Xiaomi Miio."""
import asyncio
import binascii
import logging
import socket
from typing import List

from construct import ConstructError
from miio import Device, Message
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

CONF_MODEL = "model"
CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)

DOMAIN = "xiaomi_miio"

DISCOVERY_SOCKET_ADDR = ("<broadcast>", 54321)
DISCOVERY_TIMEOUT = 3  # seconds
DISCOVERY_HELLO_MESSAGE = bytes.fromhex(
    "21310020ffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
)

SUPPORTED_DEVICES = {"philips.light.bulb": "light"}


async def async_setup(hass, config):
    """Set up the Xiaomi component."""

    discovered_devices = await discover_miio_devices()
    for device in discovered_devices:
        device_info = await hass.async_add_executor_job(device.info)
        try:
            platform = SUPPORTED_DEVICES[device_info.model]
        except KeyError:
            _LOGGER.warning("Unsupported MIIO device model: %s", device_info.model)
            continue

        info = {
            CONF_HOST: device.ip,
            CONF_TOKEN: binascii.hexlify(device.token).decode(),
            CONF_MODEL: device_info.model,
            CONF_NAME: make_device_name(device_info.model, device_info.mac_address),
        }
        discovery.load_platform(hass, platform, DOMAIN, info, config)

    return True


class DiscoveryProto:
    """Protocol to discover mmio devices in local network."""

    def __init__(self):
        """Construct an instance."""

        self.transport = None
        self._seen_addrs: List[str] = []
        self._devices: List[Device] = []
        self.devices_discovered = asyncio.get_event_loop().create_future()

    def connection_made(self, trans):
        """Handle new connection."""

        self.transport = trans
        self.transport.sendto(DISCOVERY_HELLO_MESSAGE, DISCOVERY_SOCKET_ADDR)

    def datagram_received(self, data, addr):
        """Handle incoming response."""

        if addr[0] in self._seen_addrs:
            return

        try:
            message = Message.parse(data)  # type: Message
        except ConstructError as ex:
            _LOGGER.warning("Error while reading discover results: %s", ex)
            return

        token = binascii.hexlify(message.checksum).decode()
        self._seen_addrs.append(addr[0])
        self._devices.append(Device(ip=addr[0], token=token))
        _LOGGER.debug("  IP %s - token: %s", addr[0], token)

    def error_received(self, exc):
        """Handle errors."""

        _LOGGER.warning("Error received: %s", exc)
        self.devices_discovered.set_result(self._devices)
        self.transport.close()

    def connection_lost(self, exc):
        """Handle connection closed by other side."""

        self.devices_discovered.set_result(self._devices)
        self.transport.close()


async def discover_miio_devices():
    """Asyncronously discover available devices by sending broadcast UDP packet."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(DiscoveryProto, sock=sock)
    loop.call_later(DISCOVERY_TIMEOUT, transport.close)

    return await protocol.devices_discovered


def make_device_name(model: str, mac: str) -> str:
    """Generate well-formed unique device name."""

    pretty_mac = "".join(mac.split(":"))[-4:]
    pretty_model = " ".join(s.capitalize() for s in model.split("."))
    return f"Xiaomi {pretty_model} {pretty_mac}"
