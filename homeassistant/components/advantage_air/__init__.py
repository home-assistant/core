"""Advantage Air climate integration."""

import collections.abc
from datetime import timedelta
import logging

from advantage_air import advantage_air

from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ADVANTAGE_AIR_RETRY, DOMAIN

ADVANTAGE_AIR_SYNC_INTERVAL = 15
ADVANTAGE_AIR_PLATFORMS = ["climate", "binary_sensor", "sensor", "cover", "switch"]

_LOGGER = logging.getLogger(__name__)


def update(original, updates):
    """Deep update a dictionary."""
    for key, val in updates.items():
        if isinstance(val, collections.abc.Mapping):
            original[key] = update(original.get(key, {}), val)
        else:
            original[key] = val
    return original


async def async_setup(hass, config):
    """Set up AdvantageAir."""
    hass.data[DOMAIN] = {}
    for platform in ADVANTAGE_AIR_PLATFORMS:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(platform, DOMAIN, {}, config)
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up AdvantageAir Config."""
    ip_address = config_entry.data[CONF_IP_ADDRESS]
    port = config_entry.data[CONF_PORT]
    api = advantage_air(ip_address, port, ADVANTAGE_AIR_RETRY)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="AdvantageAir",
        update_method=api.async_get,
        update_interval=timedelta(seconds=ADVANTAGE_AIR_SYNC_INTERVAL),
    )

    # Fetch initial data so we have data when entities subscribe
    while not coordinator.data:
        await coordinator.async_refresh()

    if "system" in coordinator.data:
        device = {
            "identifiers": {(DOMAIN, coordinator.data["system"]["rid"])},
            "name": coordinator.data["system"]["name"],
            "manufacturer": "Advantage Air",
            "model": coordinator.data["system"]["sysType"],
            "sw_version": coordinator.data["system"]["myAppRev"],
        }
    else:
        device = None

    async def async_change(change):
        queued = await api.async_change(change)
        if not queued:
            await coordinator.async_refresh()
        return

    hass.data[DOMAIN][ip_address] = {
        "coordinator": coordinator,
        "async_change": async_change,
        "device": device,
    }

    # Setup Platforms
    for platform in ADVANTAGE_AIR_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True
