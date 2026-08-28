"""UniFi network device discovery."""

from collections.abc import Mapping
from dataclasses import fields
from datetime import timedelta
import logging
from typing import Any

from unifi_discovery import AIOUnifiScanner, UnifiDevice

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.hass_dict import HassKey

from .const import CONSUMER_MAPPING, DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = timedelta(minutes=60)

DATA_DISCOVERY_STARTED: HassKey[bool] = HassKey(DOMAIN)


def _announced_ips(device: UnifiDevice) -> list[str]:
    """Return the IPs a device announced as its own.

    A console answers discovery on every VLAN interface it has and lists them
    in ``ip_info`` as ``"mac;ip"``, alongside ``primary_addr``. Only one of
    those answers survives the scanner's per-MAC collapse, so consumers cannot
    rely on ``source_ip`` being the address an entry was configured with.

    ``ip_info`` also carries addresses that are not the device's own: the
    upstream WAN, neighbouring hosts and all-zero placeholders. A device's
    interface MACs share the first five octets with ``hw_addr``, which is what
    separates them. Matching on the OUI alone would pull in every other
    Ubiquiti device on the network.
    """
    if not device.hw_addr:
        return []
    prefix = format_mac(device.hw_addr)[:14]
    announced = [*(device.ip_info or ())]
    if device.primary_addr:
        announced.append(device.primary_addr)
    ips: list[str] = []
    for address in announced:
        mac_address, _, ip_address = address.rpartition(";")
        if ip_address and format_mac(mac_address).startswith(prefix):
            ips.append(ip_address)
    return list(dict.fromkeys(ips))


def _device_to_dict(device: UnifiDevice) -> dict[str, Any]:
    """Convert a UnifiDevice to a plain dict.

    Avoid dataclasses.asdict() because it calls copy.deepcopy() on non-builtin
    types.  On Python 3.14+ deepcopy cannot pickle mappingproxy objects, and
    Enum members (used as dict keys in ``services``) internally reference
    ``__members__`` which is a mappingproxy.  This causes asdict() to crash
    with ``TypeError: cannot pickle 'mappingproxy' object``.
    """
    data: dict[str, Any] = {}
    for f in fields(device):
        value = getattr(device, f.name)
        if isinstance(value, Mapping):
            value = dict(value)
        data[f.name] = value
    data["announced_ips"] = _announced_ips(device)
    return data


@callback
def async_start_discovery(hass: HomeAssistant) -> None:
    """Start discovery of UniFi devices."""
    if hass.data.get(DATA_DISCOVERY_STARTED):
        return
    hass.data[DATA_DISCOVERY_STARTED] = True

    async def _async_discovery() -> None:
        async_trigger_discovery(hass, await async_discover_devices())

    @callback
    def _async_start_background_discovery(*_: Any) -> None:
        """Run discovery in the background."""
        hass.async_create_background_task(
            _async_discovery(), "unifi_discovery-discovery"
        )

    # Do not block startup since discovery takes 31s or more
    _async_start_background_discovery()
    async_track_time_interval(
        hass,
        _async_start_background_discovery,
        DISCOVERY_INTERVAL,
        cancel_on_shutdown=True,
    )


async def async_discover_devices() -> list[UnifiDevice]:
    """Discover UniFi devices on the network."""
    scanner = AIOUnifiScanner()
    devices = await scanner.async_scan()
    _LOGGER.debug("Found devices: %s", devices)
    return devices


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[UnifiDevice],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        if not device.hw_addr:
            continue
        for service, domain in CONSUMER_MAPPING.items():
            if device.services.get(service):
                discovery_flow.async_create_flow(
                    hass,
                    domain,
                    context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                    data=_device_to_dict(device),
                )
