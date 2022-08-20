"""Scan for LAN Gateways"""

import asyncio
import logging

from homeassistant.components.zeroconf import info_from_service
from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf

from .util import format_connection

connection_dict = {}

_LOGGER = logging.getLogger(__name__)


def on_service_state_change(
        zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
) -> None:
    """This callback function is triggered when a gateway device is found"""
    global connection_dict
    if state_change is ServiceStateChange.Added or state_change is ServiceStateChange.Updated:
        discovery_info = zeroconf.get_service_info(service_type, name)
        _LOGGER.warning("state_change : %s ; data : %s", state_change, discovery_info)
        if discovery_info is not None:
            discovery_info = info_from_service(discovery_info)
            service_type = service_type[:-1]
            name = name.replace(f".{service_type}.", "")
            connection = format_connection(discovery_info)
            connection_dict[name] = connection
    elif state_change is ServiceStateChange.Removed:
        _LOGGER.warning("state_change : %s", state_change)
        service_type = service_type[:-1]
        name = name.replace(f".{service_type}.", "")
        del connection_dict[name]

    _LOGGER.warning("change on_service_state_change : %s", connection_dict)


async def scan_and_get_connection_dict(timeout):
    """Search a list of gateways within a specified time range"""
    return await scan_commpn(scan_type="dict", timeout=timeout)


async def scan_commpn(scan_type: str, timeout: int, name=None):
    """scan gateway"""
    global connection_dict
    zc = Zeroconf(ip_version=IPVersion.All)
    zc.start()
    services = ["_mqtt._tcp.local."]
    kwargs = {'handlers': [on_service_state_change]}
    browser = ServiceBrowser(zc, services, **kwargs)  # type: ignore

    connection = None
    time1 = 1

    if scan_type == "dict":
        while True:
            if time1 > timeout:
                break
            await asyncio.sleep(1)
            time1 = time1 + 1

        if browser is not None:
            browser.cancel()

        if zc is not None:
            zc.close()

        return connection_dict

    else:
        while True:
            if time1 > timeout:
                break
            await asyncio.sleep(1)
            if name in connection_dict:
                connection = connection_dict[name]
            time1 = time1 + 1

        if browser is not None:
            browser.cancel()

        if zc is not None:
            zc.close()

        return connection


async def scan_and_get_connection_info(name: str, timeout: int):
    return await scan_commpn(scan_type="info", name=name, timeout=timeout)
