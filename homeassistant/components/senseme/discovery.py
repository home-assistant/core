"""The SenseME integration discovery."""
from __future__ import annotations

import asyncio

from aiosenseme import SensemeDevice, SensemeDiscovery

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME
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


async def async_discover(hass: HomeAssistant, timeout: float) -> list[SensemeDevice]:
    """Discovery devices or return them if already running."""
    if async_start_discovery(hass):
        await asyncio.sleep(timeout)
    discovery: SensemeDiscovery = hass.data[DOMAIN][DISCOVERY]
    devices: list[SensemeDevice] = discovery.devices
    return devices


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: list[SensemeDevice],
) -> None:
    """Trigger config flows for discovered devices."""
    for device in discovered_devices:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_DISCOVERY},
                data={
                    CONF_HOST: device.address,
                    CONF_ID: device.uuid,
                    CONF_NAME: device.name,
                },
            )
        )
