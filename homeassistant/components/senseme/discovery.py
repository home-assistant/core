"""The SenseME integration discovery."""
from __future__ import annotations

import asyncio

from aiosenseme import SensemeDevice, SensemeDiscovery

from homeassistant import config_entries
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback

from .const import DISCOVERY, DOMAIN


@callback
def async_start_discovery(hass: HomeAssistant) -> bool:
    """Start discovery if its not already running."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DISCOVERY in domain_data:
        return False  # already running
    discovery = domain_data[DISCOVERY] = SensemeDiscovery(False)
    discovery.add_callback(lambda devices: async_trigger_discovery(hass, devices))
    discovery.start()
    return True  # started


@callback
def async_get_discovered_device(hass: HomeAssistant, uuid: str) -> SensemeDevice:
    """Return a discovered device."""
    discovery: SensemeDiscovery = hass.data[DOMAIN][DISCOVERY]
    devices: list[SensemeDevice] = discovery.devices
    for discovered_device in devices:
        if discovered_device.uuid == uuid:
            return discovered_device
    raise RuntimeError("Discovered device unexpectedly disappeared")


async def async_discover(hass: HomeAssistant, timeout: float) -> list[SensemeDevice]:
    """Discover devices or restart it if its already running."""
    started = async_start_discovery(hass)
    discovery: SensemeDiscovery = hass.data[DOMAIN][DISCOVERY]
    if not started:  # already running
        discovery.stop()
        discovery.start()
    await asyncio.sleep(timeout)
    devices: list[SensemeDevice] = discovery.devices
    return devices


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[SensemeDevice],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        if device.uuid:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                    data={CONF_ID: device.uuid},
                )
            )
