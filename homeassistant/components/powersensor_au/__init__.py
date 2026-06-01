"""The Powersensor integration."""

from datetime import datetime, timedelta
import logging

from powersensor_local import VirtualHousehold
from powersensor_local.devices import PowersensorDevices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import Event, HassJob, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .config_flow import PowersensorConfigFlow
from .const import CFG_ROLES, ROLE_SOLAR
from .models import PowersensorConfigEntry, PowersensorRuntimeData
from .powersensor_message_dispatcher import PowersensorMessageDispatcher

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

RESCAN_INTERVAL = timedelta(minutes=5)

# One-shot rescan delays (seconds) after startup.  The initial UDP scan window
# is only 2 seconds, so plugs that are slow to respond on boot get multiple
# additional chances before the regular 5-minute interval takes over.
_STARTUP_RESCAN_DELAYS = (10, 30, 60, 120)


async def async_setup_entry(hass: HomeAssistant, entry: PowersensorConfigEntry) -> bool:
    """Set up integration from a config entry."""
    try:
        with_solar = ROLE_SOLAR in entry.data.get(CFG_ROLES, {}).values()
        vhh = VirtualHousehold(with_solar)
        dispatcher = PowersensorMessageDispatcher(hass, entry, vhh)
        devices = PowersensorDevices()
    except (KeyError, ValueError, HomeAssistantError) as err:
        raise ConfigEntryNotReady(f"Unexpected error during setup: {err}") from err

    entry.runtime_data = PowersensorRuntimeData(
        vhh=vhh,
        dispatcher=dispatcher,
        devices=devices,
    )

    # Register platform signal listeners before starting discovery so that
    # device_found events fired during devices.start() land on ready listeners.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start the unified device event stream.  devices.start() runs the UDP
    # broadcast scan and fires device_found for every responding plug before
    # returning.  The platform is already set up above so those signals are
    # handled immediately.
    try:
        await devices.start(dispatcher.on_device_event)
    except (OSError, HomeAssistantError, RuntimeError) as err:
        await devices.stop()
        raise ConfigEntryNotReady(f"Failed to start device discovery: {err}") from err

    async def _rescan(_now: datetime) -> None:
        await devices.rescan()

    # Short-interval one-shot rescans catch plugs that missed the initial
    # 2-second UDP window (e.g. still booting when HA started).
    for delay in _STARTUP_RESCAN_DELAYS:
        entry.async_on_unload(async_call_later(hass, delay, HassJob(_rescan)))

    # Periodic rescan picks up new plugs and IP changes indefinitely.
    entry.async_on_unload(async_track_time_interval(hass, _rescan, RESCAN_INTERVAL))

    # After a laptop sleep/wake the asyncio event loop is suspended for the
    # duration of the sleep.  The library's expiry timer fires immediately on
    # wake (its deadline is long past) and removes all devices from its internal
    # _devices dict, then the next rescan re-adds them and fires device_found
    # again.  The dispatcher handles this correctly: on a duplicate device_found
    # it skips the CREATE signal (no duplicate entities) but still calls
    # devices.subscribe(mac) to re-arm the fresh _Device object, which starts
    # with subscribed=False.  The library also orphans the old PlugApi when it
    # creates a new one for the same MAC on rescan (_plug_apis is not cleaned up
    # in _remove_device), but both connections deliver identical data through the
    # same _reemit path and the subscribed flag is shared via _devices, so the
    # duplicate connection is harmless — events simply arrive twice with the same
    # value.  The full recovery path is therefore fully guarded in this component.
    async def _on_hass_started(_event: Event) -> None:
        _LOGGER.debug("HA started event — triggering Powersensor rescan")
        await devices.rescan()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_hass_started)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PowersensorConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        runtime = entry.runtime_data
        await runtime.dispatcher.disconnect()
        await runtime.devices.stop()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry."""
    _LOGGER.debug("Upgrading config from %s.%s", entry.version, entry.minor_version)
    if entry.version > PowersensorConfigFlow.VERSION:
        return False

    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry, data={CFG_ROLES: {}}, version=2, minor_version=2
        )

    _LOGGER.debug("Upgraded config to %s.%s", entry.version, entry.minor_version)
    return True
