"""UniFi network device discovery."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from datetime import timedelta
import logging
from typing import Any

from unifi_discovery import AIOUnifiScanner, UnifiDevice

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.hass_dict import HassKey

from .const import CONSUMER_MAPPING, DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = timedelta(minutes=60)

DATA_DISCOVERY_STARTED: HassKey[bool] = HassKey(DOMAIN)


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
