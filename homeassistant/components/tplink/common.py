"""Common code for tplink."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
from typing import Callable

from pyHS100 import (
    Discover as BaseDiscover,
    SmartBulb,
    SmartDevice,
    SmartDeviceException,
    SmartPlug,
    SmartStrip,
    TPLinkSmartHomeProtocol,
)

from homeassistant.components import network
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_DIMMER,
    CONF_LIGHT,
    CONF_STRIP,
    CONF_SWITCH,
    DOMAIN as TPLINK_DOMAIN,
    MAX_DISCOVERY_RETRIES,
)

_LOGGER = logging.getLogger(__name__)


class SmartDevices:
    """Hold different kinds of devices."""

    def __init__(
        self, lights: list[SmartDevice] = None, switches: list[SmartDevice] = None
    ) -> None:
        """Initialize device holder."""
        self._lights = lights or []
        self._switches = switches or []

    @property
    def lights(self) -> list[SmartDevice]:
        """Get the lights."""
        return self._lights

    @property
    def switches(self) -> list[SmartDevice]:
        """Get the switches."""
        return self._switches

    def has_device_with_host(self, host: str) -> bool:
        """Check if a devices exists with a specific host."""
        for device in self.lights + self.switches:
            if device.host == host:
                return True

        return False


class Discover(BaseDiscover):
    """Discover TPLink Smart Home devices.

    The main entry point for this class is Discover.discover(),
    which returns a dictionary of the found devices. The key is the IP address
    of the device and the value contains ready-to-use, SmartDevice-derived
    device object.

    This version overrides the base class in order to allow
    the target network address to be specified.
    """

    @staticmethod
    def discover_target(
        protocol: TPLinkSmartHomeProtocol = None,
        target: str = "255.255.255.255",
        port: int = 9999,
        timeout: int = 3,
        discovery_packets=3,
        return_raw=False,
    ) -> dict[str, SmartDevice]:
        """
        Discover TPLink Smart Home devices.

        Sends discovery message to the specified broadcast address in order
        to detect available supported devices in the local network,
        and waits for given timeout for answers from devices.
        :param protocol: Protocol implementation to use
        :param target: The target broadcast address (e.g. 192.168.xxx.255).
        :param timeout: How long to wait for responses, defaults to 3
        :param port: port to send broadcast messages, defaults to 9999.
        :rtype: dict
        :return: Array of json objects {"ip", "port", "sys_info"}
        """
        if protocol is None:
            protocol = TPLinkSmartHomeProtocol()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)

        req = json.dumps(Discover.DISCOVERY_QUERY)
        _LOGGER.debug("Sending discovery to %s:%s", target, port)

        encrypted_req = protocol.encrypt(req)
        for _ in range(discovery_packets):
            sock.sendto(encrypted_req[4:], (target, port))

        devices = {}
        _LOGGER.debug("Waiting %s seconds for responses", timeout)

        try:
            while True:
                data, addr = sock.recvfrom(4096)
                ip_addr, port = addr
                info = json.loads(protocol.decrypt(data))
                device_class = Discover._get_device_class(info)
                if return_raw:
                    devices[ip_addr] = info
                elif device_class is not None:
                    devices[ip_addr] = device_class(ip_addr)
        except socket.timeout:
            _LOGGER.debug("Got socket timeout, which is okay")
        _LOGGER.debug("Found %s devices: %s", len(devices), devices)
        return devices


async def async_get_discoverable_devices(hass: HomeAssistant) -> dict[str, SmartDevice]:
    """Return if there are devices that can be discovered."""

    def discover(target) -> dict[str, SmartDevice]:
        return Discover.discover_target(target=target)

    targets = []
    adapters = await network.async_get_adapters(hass)
    for adapter in adapters:
        if adapter["enabled"]:
            for ip_info in adapter["ipv4"]:
                iface = ipaddress.ip_interface(
                    f"{ip_info['address']}/{ip_info['network_prefix']}"
                )
                targets.append(iface.network.broadcast_address.exploded)

    all_devs = await asyncio.gather(
        *(hass.async_add_executor_job(discover, t) for t in targets)
    )

    devs = {}
    for target_devs in all_devs:
        devs.update(target_devs)

    return devs


async def async_discover_devices(
    hass: HomeAssistant, existing_devices: SmartDevices, target_device_count: int
) -> SmartDevices:
    """Get devices through discovery."""

    lights = []
    switches = []

    def process_devices() -> None:
        for dev in devices.values():
            # If this device already exists, ignore dynamic setup.
            if existing_devices.has_device_with_host(dev.host):
                continue

            if isinstance(dev, SmartStrip):
                for plug in dev.plugs.values():
                    switches.append(plug)
            elif isinstance(dev, SmartPlug):
                try:
                    if dev.is_dimmable:  # Dimmers act as lights
                        lights.append(dev)
                    else:
                        switches.append(dev)
                except SmartDeviceException as ex:
                    _LOGGER.error("Unable to connect to device %s: %s", dev.host, ex)

            elif isinstance(dev, SmartBulb):
                lights.append(dev)
            else:
                _LOGGER.error("Unknown smart device type: %s", type(dev))

    devices: dict[str, SmartDevice] = {}
    for attempt in range(1, MAX_DISCOVERY_RETRIES + 1):
        _LOGGER.debug(
            "Discovering tplink devices, attempt %s of %s",
            attempt,
            MAX_DISCOVERY_RETRIES,
        )
        discovered_devices = await async_get_discoverable_devices(hass)
        _LOGGER.info(
            "Discovered %s TP-Link of expected %s smart home device(s)",
            len(discovered_devices),
            target_device_count,
        )
        for device_ip in discovered_devices:
            devices[device_ip] = discovered_devices[device_ip]

        if len(discovered_devices) >= target_device_count:
            _LOGGER.info(
                "Discovered at least as many devices on the network as exist in our device registry, no need to retry"
            )
            break

    _LOGGER.info(
        "Found %s unique TP-Link smart home device(s) after %s discovery attempts",
        len(devices),
        attempt,
    )
    await hass.async_add_executor_job(process_devices)

    return SmartDevices(lights, switches)


def get_static_devices(config_data) -> SmartDevices:
    """Get statically defined devices in the config."""
    _LOGGER.debug("Getting static devices")
    lights = []
    switches = []

    for type_ in (CONF_LIGHT, CONF_SWITCH, CONF_STRIP, CONF_DIMMER):
        for entry in config_data[type_]:
            host = entry["host"]
            try:
                if type_ == CONF_LIGHT:
                    lights.append(SmartBulb(host))
                elif type_ == CONF_SWITCH:
                    switches.append(SmartPlug(host))
                elif type_ == CONF_STRIP:
                    for plug in SmartStrip(host).plugs.values():
                        switches.append(plug)
                # Dimmers need to be defined as smart plugs to work correctly.
                elif type_ == CONF_DIMMER:
                    lights.append(SmartPlug(host))
            except SmartDeviceException as sde:
                _LOGGER.error(
                    "Failed to setup device %s due to %s; not retrying", host, sde
                )
    return SmartDevices(lights, switches)


def add_available_devices(
    hass: HomeAssistant, device_type: str, device_class: Callable
) -> list[Entity]:
    """Get sysinfo for all devices."""

    devices: list[SmartDevice] = hass.data[TPLINK_DOMAIN][device_type]

    if f"{device_type}_remaining" in hass.data[TPLINK_DOMAIN]:
        devices: list[SmartDevice] = hass.data[TPLINK_DOMAIN][
            f"{device_type}_remaining"
        ]

    entities_ready: list[Entity] = []
    devices_unavailable: list[SmartDevice] = []
    for device in devices:
        try:
            device.get_sysinfo()
            entities_ready.append(device_class(device))
        except SmartDeviceException as ex:
            devices_unavailable.append(device)
            _LOGGER.warning(
                "Unable to communicate with device %s: %s",
                device.host,
                ex,
            )

    hass.data[TPLINK_DOMAIN][f"{device_type}_remaining"] = devices_unavailable
    return entities_ready
