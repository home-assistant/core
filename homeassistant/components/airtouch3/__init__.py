"""The AirTouch 3 Air Conditioner integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DISCOVERY_INTERVAL, DISCOVERY_TIMEOUT, DOMAIN
from .coordinator import Airtouch3DataUpdateCoordinator
from .discovery import async_discover_devices, async_trigger_discovery

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CLIMATE]
type AirTouch3ConfigEntry = ConfigEntry[Airtouch3DataUpdateCoordinator]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up AirTouch 3 discovery."""

    @callback
    def _async_start_background_discovery(*_: Any) -> None:
        hass.async_create_background_task(
            _async_discovery(), "airtouch3-discovery", eager_start=True
        )

    async def _async_discovery() -> None:
        async_trigger_discovery(
            hass, await async_discover_devices(hass, DISCOVERY_TIMEOUT)
        )

    _async_start_background_discovery()
    async_track_time_interval(
        hass,
        _async_start_background_discovery,
        DISCOVERY_INTERVAL,
        cancel_on_shutdown=True,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AirTouch3ConfigEntry) -> bool:
    """Set up AirTouch 3 Air Conditioner from a config entry."""
    host = entry.data[CONF_HOST]
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, host)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    if not entry.unique_id and coordinator.data.aircon.system_id:
        hass.config_entries.async_update_entry(
            entry, unique_id=coordinator.data.aircon.system_id
        )

    _LOGGER.debug("Setting up AirTouch 3 at %s", host)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirTouch3ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
