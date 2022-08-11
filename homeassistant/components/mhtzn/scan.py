import asyncio
import logging

from homeassistant.components.zeroconf import ZeroconfServiceInfo, info_from_service
from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf, ZeroconfServiceTypes, DNSQuestionType
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser, AsyncServiceInfo

from custom_components.mhtzn.util import get_name, get_connection_dict

search_map = {}

_LOGGER = logging.getLogger(__name__)


def on_service_state_change(
        zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
) -> None:
    global search_map
    if state_change is ServiceStateChange.Added or state_change is ServiceStateChange.Updated:
        info = zeroconf.get_service_info(service_type, name)
        _LOGGER.warning("state_change : %s ; data : %s", state_change, info)
        if info is not None:
            discovery_info = info_from_service(info)
            service_type = service_type[:-1]
            name = name.replace(f".{service_type}.", "")
            connection_dict = get_connection_dict(discovery_info)
            search_map[name] = connection_dict
    elif state_change is ServiceStateChange.Removed:
        _LOGGER.warning("state_change : %s", state_change)
        service_type = service_type[:-1]
        name = name.replace(f".{service_type}.", "")
        del search_map[name]

    _LOGGER.warning("change on_service_state_change : %s", search_map)


async def scan_gateway_dict(timeout):
    global search_map
    search_map = {}
    zc = Zeroconf(ip_version=IPVersion.All)
    zc.start()
    services = ["_mqtt._tcp.local."]
    kwargs = {'handlers': [on_service_state_change]}
    browser = ServiceBrowser(zc, services, **kwargs)  # type: ignore

    _LOGGER.warning("开始执行扫描")
    time1 = 1
    while True:
        if time1 > timeout:
            break
        await asyncio.sleep(1)
        time1 = time1 + 1

    if browser is not None:
        browser.cancel()

    if zc is not None:
        zc.close()

    return search_map


async def scan_gateway_info(name: str, timeout: int):
    global search_map
    search_map = {}
    zc = Zeroconf(ip_version=IPVersion.All)
    zc.start()
    services = ["_mqtt._tcp.local."]
    kwargs = {'handlers': [on_service_state_change]}
    browser = ServiceBrowser(zc, services, **kwargs)  # type: ignore

    _LOGGER.warning("开始执行扫描")

    connection = None
    time1 = 1
    while True:
        if time1 > timeout:
            break
        await asyncio.sleep(1)
        if name in search_map:
            connection = search_map[name]
        time1 = time1 + 1

    if browser is not None:
        browser.cancel()

    if zc is not None:
        zc.close()

    return connection
