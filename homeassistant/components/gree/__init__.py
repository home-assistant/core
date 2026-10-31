"""The Gree Climate integration."""

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DISCOVERY_SCAN_INTERVAL, DOMAIN
from .coordinator import DeviceDataUpdateCoordinator, GreeConfigEntry
from .discovery import async_get_discovery, device_info_to_data
from .migration import async_migrate_legacy_entry, async_reconcile_migrated_entry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Schedule domain-wide discovery without enrolling devices."""
    discovery = async_get_discovery(hass)

    @callback
    def _async_stop(_event: Event) -> None:
        discovery.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)

    async def _async_discovery(_now: datetime | None = None) -> None:
        try:
            devices = await discovery.async_scan()
        except OSError, TimeoutError:
            _LOGGER.warning("Unable to discover Gree devices", exc_info=True)
            return
        if hass.is_stopping:
            return
        for info in devices.values():
            discovery_flow.async_create_flow(
                hass,
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data=device_info_to_data(info),
            )

    hass.async_create_background_task(
        _async_discovery(), "gree first discovery", eager_start=True
    )
    async_track_time_interval(
        hass,
        _async_discovery,
        timedelta(seconds=DISCOVERY_SCAN_INTERVAL),
        cancel_on_shutdown=True,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Set up Gree Climate from a config entry."""
    async_reconcile_migrated_entry(hass, entry)
    if entry.version == 1:
        # Empty legacy entries anchor discovery until a device returns.
        return
    if not entry.data[CONF_HOST]:
        raise ConfigEntryNotReady("Waiting for discovery of the migrated Gree device")

    entry.runtime_data = coordinator = DeviceDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Convert legacy registry ownership before starting any connections."""
    if entry.version == 1:
        await async_migrate_legacy_entry(hass, entry)
