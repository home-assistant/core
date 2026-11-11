"""The Gree Climate integration."""

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
    entity_registry as er,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DISCOVERY_SCAN_INTERVAL, DOMAIN
from .coordinator import DeviceDataUpdateCoordinator, GreeConfigEntry
from .discovery import async_get_discovery, device_info_to_data

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register domain-wide discovery shutdown."""
    discovery = async_get_discovery(hass)

    @callback
    def _async_stop(_event: Event) -> None:
        discovery.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Set up Gree Climate from a config entry."""
    if entry.unique_id == DOMAIN:
        discovery = async_get_discovery(hass)
        unloaded = False

        @callback
        def _async_mark_unloaded() -> None:
            nonlocal unloaded
            unloaded = True

        async def _async_discovery() -> None:
            try:
                devices = await discovery.async_scan()
            except OSError, TimeoutError:
                _LOGGER.warning("Unable to discover Gree devices", exc_info=True)
                return
            if unloaded or hass.is_stopping:
                return
            for info in devices.values():
                discovery_flow.async_create_flow(
                    hass,
                    DOMAIN,
                    context={"source": SOURCE_INTEGRATION_DISCOVERY},
                    data=device_info_to_data(info),
                )

        @callback
        def _async_start_discovery(_now: datetime | None = None) -> None:
            entry.async_create_background_task(
                hass, _async_discovery(), "gree discovery"
            )

        entry.async_on_unload(_async_mark_unloaded)
        entry.async_on_unload(
            async_track_time_interval(
                hass,
                _async_start_discovery,
                timedelta(seconds=DISCOVERY_SCAN_INTERVAL),
                cancel_on_shutdown=True,
            )
        )
        _async_start_discovery()
        return

    entry.runtime_data = coordinator = DeviceDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Unload a config entry."""
    if entry.unique_id != DOMAIN:
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate the legacy shared entry to the persistent discovery owner."""
    if entry.version == 1:
        _LOGGER.debug("Migrating legacy Gree config entry %s", entry.entry_id)
        dr.async_get(hass).async_clear_config_entry(entry.entry_id, DOMAIN)
        er.async_get(hass).async_clear_config_entry(entry.entry_id)
        hass.config_entries.async_update_entry(
            entry,
            data={},
            minor_version=1,
            unique_id=DOMAIN,
            version=2,
        )
