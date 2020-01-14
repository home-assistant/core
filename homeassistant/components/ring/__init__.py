"""Support for Ring Doorbell/Chimes."""
import asyncio
from datetime import timedelta
from functools import partial
import logging
from pathlib import Path

from ring_doorbell import Auth, Ring
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, __version__
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.async_ import run_callback_threadsafe

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Ring.com"

NOTIFICATION_ID = "ring_notification"
NOTIFICATION_TITLE = "Ring Setup"

DATA_HEALTH_DATA_TRACKER = "ring_health_data"
DATA_TRACK_INTERVAL = "ring_track_interval"

DOMAIN = "ring"
DEFAULT_ENTITY_NAMESPACE = "ring"
SIGNAL_UPDATE_RING = "ring_update"
SIGNAL_UPDATE_HEALTH_RING = "ring_health_update"

SCAN_INTERVAL = timedelta(seconds=10)

PLATFORMS = ("binary_sensor", "light", "sensor", "switch", "camera")

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Ring component."""
    if DOMAIN not in config:
        return True

    def legacy_cleanup():
        """Clean up old tokens."""
        old_cache = Path(hass.config.path(".ring_cache.pickle"))
        if old_cache.is_file():
            old_cache.unlink()

    await hass.async_add_executor_job(legacy_cleanup)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "username": config[DOMAIN]["username"],
                "password": config[DOMAIN]["password"],
            },
        )
    )
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""

    def token_updater(token):
        """Handle from sync context when token is updated."""
        run_callback_threadsafe(
            hass.loop,
            partial(
                hass.config_entries.async_update_entry,
                entry,
                data={**entry.data, "token": token},
            ),
        ).result()

    auth = Auth(f"HomeAssistant/{__version__}", entry.data["token"], token_updater)
    ring = Ring(auth)

    await hass.async_add_executor_job(ring.update_data)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ring

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    if hass.services.has_service(DOMAIN, "update"):
        return True

    async def refresh_all(_):
        """Refresh all ring accounts."""
        await asyncio.gather(
            *[
                hass.async_add_executor_job(api.update_data)
                for api in hass.data[DOMAIN].values()
            ]
        )
        async_dispatcher_send(hass, SIGNAL_UPDATE_RING)

    # register service
    hass.services.async_register(DOMAIN, "update", refresh_all)

    # register scan interval for ring
    hass.data[DATA_TRACK_INTERVAL] = async_track_time_interval(
        hass, refresh_all, SCAN_INTERVAL
    )
    hass.data[DATA_HEALTH_DATA_TRACKER] = HealthDataUpdater(hass)

    return True


async def async_unload_entry(hass, entry):
    """Unload Ring entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not unload_ok:
        return False

    hass.data[DOMAIN].pop(entry.entry_id)

    if len(hass.data[DOMAIN]) != 0:
        return True

    # Last entry unloaded, clean up
    hass.data.pop(DATA_TRACK_INTERVAL)()
    hass.data.pop(DATA_HEALTH_DATA_TRACKER)
    hass.services.async_remove(DOMAIN, "update")

    return True


class HealthDataUpdater:
    """Data storage for health data."""

    def __init__(self, hass):
        """Track devices that need healh data updated."""
        self.hass = hass
        self.devices = {}
        self._unsub_interval = None

    async def track_device(self, config_entry_id, device):
        """Track a device."""
        if not self.devices:
            self._unsub_interval = async_track_time_interval(
                self.hass, self.refresh_all, SCAN_INTERVAL
            )

        key = (config_entry_id, device.device_id)

        if key not in self.devices:
            self.devices[key] = {
                "device": device,
                "count": 1,
            }
        else:
            self.devices[key]["count"] += 1

        await self.hass.async_add_executor_job(device.update_health_data)

    @callback
    def untrack_device(self, config_entry_id, device):
        """Untrack a device."""
        key = (config_entry_id, device.device_id)
        self.devices[key]["count"] -= 1

        if self.devices[key]["count"] == 0:
            self.devices.pop(key)

        if not self.devices:
            self._unsub_interval()
            self._unsub_interval = None

    def refresh_all(self, _):
        """Refresh all registered devices."""
        for info in self.devices.values():
            info["device"].update_health_data()

        dispatcher_send(self.hass, SIGNAL_UPDATE_HEALTH_RING)
