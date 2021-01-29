"""Support for Ezviz camera."""
import asyncio
from datetime import timedelta
import logging

from pyezviz.client import EzvizClient
from requests import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ACC_PASSWORD,
    ACC_USERNAME,
    ATTR_CAMERAS,
    CONF_FFMPEG_ARGUMENTS,
    DATA_COORDINATOR,
    DATA_UNDO_UPDATE_LISTENER,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_REGION,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .coordinator import EzvizDataUpdateCoordinator

CAMERA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

EZVIZ_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ACC_USERNAME): cv.string,
            vol.Optional(ACC_PASSWORD): cv.string,
            vol.Optional(CONF_REGION, default=DEFAULT_REGION): cv.string,
            vol.Optional(ATTR_CAMERAS, default={}): {cv.string: CAMERA_SCHEMA},
        }
    )
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: EZVIZ_SCHEMA}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

PLATFORMS = "camera"


async def async_setup(hass: HomeAssistantType, config: dict) -> bool:
    """Set up the Ezviz integration."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN, EZVIZ_SCHEMA({}))
    hass.data[DOMAIN] = {"config": conf}

    if hass.config_entries.async_entries(DOMAIN):
        return True

    if ACC_USERNAME or ACC_PASSWORD or CONF_REGION not in conf:
        return True

    if ACC_USERNAME or ACC_PASSWORD or CONF_REGION in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Ezviz from a config entry."""

    if not entry.options:
        options = {
            CONF_FFMPEG_ARGUMENTS: entry.data.get(
                CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
            ),
            CONF_TIMEOUT: entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        }
        hass.config_entries.async_update_entry(entry, options=options)

    try:
        ezviz_client = await hass.async_add_executor_job(
            _get_ezviz_client_instance, entry
        )
    except (ConnectTimeout, HTTPError) as error:
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

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, PLATFORMS)
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(entry, PLATFORMS)]
        )
    )

    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][DATA_UNDO_UPDATE_LISTENER]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistantType, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_ezviz_client_instance(entry: ConfigEntry) -> EzvizClient:
    """Initialize a new instance of EzvizClientApi."""
    ezviz_client = EzvizClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_REGION],
        entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )
    ezviz_client.login()
    return ezviz_client
