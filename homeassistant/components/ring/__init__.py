"""Support for Ring Doorbell/Chimes."""
import asyncio
from datetime import timedelta
from functools import partial
import logging
from pathlib import Path

from requests.exceptions import ConnectTimeout, HTTPError
from ring_doorbell import Ring
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Ring.com"

NOTIFICATION_ID = "ring_notification"
NOTIFICATION_TITLE = "Ring Setup"

DATA_RING_DOORBELLS = "ring_doorbells"
DATA_RING_STICKUP_CAMS = "ring_stickup_cams"
DATA_RING_CHIMES = "ring_chimes"
DATA_TRACK_INTERVAL = "ring_track_interval"

DOMAIN = "ring"
DEFAULT_CACHEDB = ".ring_cache.pickle"
DEFAULT_ENTITY_NAMESPACE = "ring"
SIGNAL_UPDATE_RING = "ring_update"

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
    cache = hass.config.path(DEFAULT_CACHEDB)
    try:
        ring = await hass.async_add_executor_job(
            partial(
                Ring,
                username=entry.data["username"],
                password="invalid-password",
                cache_file=cache,
            )
        )
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Ring service: %s", str(ex))
        hass.components.persistent_notification.async_create(
            "Error: {}<br />"
            "You will need to restart hass after fixing."
            "".format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    if not ring.is_connected:
        _LOGGER.error("Unable to connect to Ring service")
        return False

    await hass.async_add_executor_job(finish_setup_entry, hass, ring)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


def finish_setup_entry(hass, ring):
    """Finish setting up entry."""
    hass.data[DATA_RING_CHIMES] = chimes = ring.chimes
    hass.data[DATA_RING_DOORBELLS] = doorbells = ring.doorbells
    hass.data[DATA_RING_STICKUP_CAMS] = stickup_cams = ring.stickup_cams

    ring_devices = chimes + doorbells + stickup_cams

    def service_hub_refresh(service):
        hub_refresh()

    def timer_hub_refresh(event_time):
        hub_refresh()

    def hub_refresh():
        """Call ring to refresh information."""
        _LOGGER.debug("Updating Ring Hub component")

        for camera in ring_devices:
            _LOGGER.debug("Updating camera %s", camera.name)
            camera.update()

        dispatcher_send(hass, SIGNAL_UPDATE_RING)

    # register service
    hass.services.register(DOMAIN, "update", service_hub_refresh)

    # register scan interval for ring
    hass.data[DATA_TRACK_INTERVAL] = track_time_interval(
        hass, timer_hub_refresh, SCAN_INTERVAL
    )


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

    await hass.async_add_executor_job(hass.data[DATA_TRACK_INTERVAL])

    hass.services.async_remove(DOMAIN, "update")

    hass.data.pop(DATA_RING_DOORBELLS)
    hass.data.pop(DATA_RING_STICKUP_CAMS)
    hass.data.pop(DATA_RING_CHIMES)
    hass.data.pop(DATA_TRACK_INTERVAL)

    return unload_ok


async def async_remove_entry(hass, entry):
    """Act when an entry is removed."""
    await hass.async_add_executor_job(Path(hass.config.path(DEFAULT_CACHEDB)).unlink)
