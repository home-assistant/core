"""Support for Canary devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from canary.api import Api
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FFMPEG_ARGUMENTS,
    DATA_COORDINATOR,
    DATA_UNDO_UPDATE_LISTENER,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .coordinator import CanaryDataUpdateCoordinator

_LOGGER: Final = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES: Final = timedelta(seconds=30)

CONFIG_SCHEMA: Final = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(
                        CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                    ): cv.positive_int,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: Final[list[Platform]] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.CAMERA,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Canary integration."""
    hass.data.setdefault(DOMAIN, {})

    if hass.config_entries.async_entries(DOMAIN):
        return True

    ffmpeg_arguments = DEFAULT_FFMPEG_ARGUMENTS
    if CAMERA_DOMAIN in config:
        camera_config = next(
            (item for item in config[CAMERA_DOMAIN] if item["platform"] == DOMAIN),
            None,
        )

        if camera_config:
            ffmpeg_arguments = camera_config.get(
                CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
            )

    if DOMAIN in config:
        if ffmpeg_arguments != DEFAULT_FFMPEG_ARGUMENTS:
            config[DOMAIN][CONF_FFMPEG_ARGUMENTS] = ffmpeg_arguments

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Canary from a config entry."""
    if not entry.options:
        options = {
            CONF_FFMPEG_ARGUMENTS: entry.data.get(
                CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
            ),
            CONF_TIMEOUT: entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        }
        hass.config_entries.async_update_entry(entry, options=options)

    try:
        canary_api = await hass.async_add_executor_job(_get_canary_api_instance, entry)
    except (ConnectTimeout, HTTPError) as error:
        _LOGGER.error("Unable to connect to Canary service: %s", str(error))
        raise ConfigEntryNotReady from error

    coordinator = CanaryDataUpdateCoordinator(hass, api=canary_api)
    await coordinator.async_config_entry_first_refresh()

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_UNDO_UPDATE_LISTENER: undo_listener,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][DATA_UNDO_UPDATE_LISTENER]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_canary_api_instance(entry: ConfigEntry) -> Api:
    """Initialize a new instance of CanaryApi."""
    return Api(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )
