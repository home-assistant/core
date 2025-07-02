"""Support for Canary devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from canary.api import Api
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS, DEFAULT_TIMEOUT
from .coordinator import CanaryConfigEntry, CanaryDataUpdateCoordinator

_LOGGER: Final = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES: Final = timedelta(seconds=30)

PLATFORMS: Final[list[Platform]] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.CAMERA,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: CanaryConfigEntry) -> bool:
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

    coordinator = CanaryDataUpdateCoordinator(hass, entry, api=canary_api)
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CanaryConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: CanaryConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_canary_api_instance(entry: CanaryConfigEntry) -> Api:
    """Initialize a new instance of CanaryApi."""
    return Api(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )
