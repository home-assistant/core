"""The pylontech_us integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .pylontech_us_coordinator import PylontechUsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# currently needs to be run with:
# pip install git+https://github.com/danielschramm/pylontech-python.git@url_issues


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up pylontech_us from a config entry."""
    # TOODOO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    port = config_entry.data["pylontech_us_port"]
    baud = config_entry.data["pylontech_us_baud"]
    battery_count = config_entry.data["pylontech_us_battery_count"]

    coordinator = PylontechUsCoordinator(
        hass, port=port, baud=baud, battery_count=battery_count
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
