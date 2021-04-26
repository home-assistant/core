"""Support for Ezviz camera."""
import asyncio
from datetime import timedelta
import logging

from pyezviz.client import EzvizClient, HTTPError, InvalidURL, PyEzvizError

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    DATA_COORDINATOR,
    DATA_UNDO_UPDATE_LISTENER,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .coordinator import EzvizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

PLATFORMS = [
    "binary_sensor",
    "camera",
    "sensor",
    "switch",
]


async def async_setup_entry(hass, entry):
    """Set up Ezviz from a config entry."""
    if not entry.options:
        options = {
            CONF_FFMPEG_ARGUMENTS: entry.data.get(
                CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
            ),
            CONF_TIMEOUT: entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        }
        hass.config_entries.async_update_entry(entry, options=options)

    if entry.data.get(CONF_TYPE) == ATTR_TYPE_CAMERA:
        if hass.data.get(DOMAIN):
            # Should only execute on addition of new camera entry.
            # Fetch Entry id of main account and reload it.
            for item in hass.config_entries.async_entries():
                if item.data.get(CONF_TYPE) == ATTR_TYPE_CLOUD:
                    _LOGGER.info("Reload Ezviz integration with new camera rtsp entry")
                    await hass.config_entries.async_reload(item.entry_id)

        return True

    try:
        ezviz_client = await hass.async_add_executor_job(
            _get_ezviz_client_instance, entry
        )
    except (InvalidURL, HTTPError, PyEzvizError) as error:
        _LOGGER.error("Unable to connect to Ezviz service: %s", str(error))
        raise ConfigEntryNotReady from error

    coordinator = EzvizDataUpdateCoordinator(hass, api=ezviz_client)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_UNDO_UPDATE_LISTENER: undo_listener,
    }
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    if entry.data.get(CONF_TYPE) == ATTR_TYPE_CAMERA:
        return True

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][DATA_UNDO_UPDATE_LISTENER]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_ezviz_client_instance(entry):
    """Initialize a new instance of EzvizClientApi."""
    ezviz_client = EzvizClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_URL],
        entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )
    ezviz_client.login()
    return ezviz_client
