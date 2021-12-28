"""The SenseME integration."""
from __future__ import annotations

from typing import Any

from aiosenseme import SensemeDevice, async_get_device_by_device_info, discover_all

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_ID, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_INFO,
    DISCOVER_SCAN_TIMEOUT,
    DISCOVERY,
    DISCOVERY_INTERVAL,
    DOMAIN,
    PLATFORMS,
    STARTUP_SCAN_TIMEOUT,
    UPDATE_RATE,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SenseME component."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[DISCOVERY] = await discover_all(STARTUP_SCAN_TIMEOUT)

    async def _async_discovery(*_: Any) -> None:
        async_trigger_discovery(hass, await discover_all(DISCOVER_SCAN_TIMEOUT))

    async_trigger_discovery(hass, domain_data[DISCOVERY])
    async_track_time_interval(hass, _async_discovery, DISCOVERY_INTERVAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SenseME from a config entry."""
    status, device = await async_get_device_by_device_info(
        info=entry.data[CONF_INFO], start_first=True, refresh_minutes=UPDATE_RATE
    )

    if not status:
        # even if the device could not connect it will keep trying because start_first=True
        device.stop()
        raise ConfigEntryNotReady(f"Connect to address {device.address} failed")

    await device.async_update(not status)

    hass.data[DOMAIN][entry.entry_id] = {CONF_DEVICE: device}
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN][entry.entry_id][CONF_DEVICE].stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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
                    CONF_MAC: device.mac,
                    CONF_NAME: device.name,
                },
            )
        )
