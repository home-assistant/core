"""Support for UpCloud."""

from __future__ import annotations

from datetime import timedelta
import logging

import requests.exceptions
import upcloud_api

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE, DEFAULT_SCAN_INTERVAL
from .coordinator import UpCloudConfigEntry, UpCloudDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]


def _config_entry_update_signal_name(config_entry: UpCloudConfigEntry) -> str:
    """Get signal name for updates to a config entry."""
    return CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE.format(config_entry.unique_id)


async def _async_signal_options_update(
    hass: HomeAssistant, config_entry: UpCloudConfigEntry
) -> None:
    """Signal config entry options update."""
    async_dispatcher_send(
        hass, _config_entry_update_signal_name(config_entry), config_entry
    )


async def async_setup_entry(hass: HomeAssistant, entry: UpCloudConfigEntry) -> bool:
    """Set up the UpCloud config entry."""

    manager = upcloud_api.CloudManager(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )

    try:
        await hass.async_add_executor_job(manager.authenticate)
    except upcloud_api.UpCloudAPIError:
        _LOGGER.exception("Authentication failed")
        return False
    except requests.exceptions.RequestException as err:
        _LOGGER.exception("Failed to connect")
        raise ConfigEntryNotReady from err

    if entry.options.get(CONF_SCAN_INTERVAL):
        update_interval = timedelta(seconds=entry.options[CONF_SCAN_INTERVAL])
    else:
        update_interval = DEFAULT_SCAN_INTERVAL

    coordinator = UpCloudDataUpdateCoordinator(
        hass,
        config_entry=entry,
        update_interval=update_interval,
        cloud_manager=manager,
        username=entry.data[CONF_USERNAME],
    )
    entry.runtime_data = coordinator

    # Call the UpCloud API to refresh data
    await coordinator.async_config_entry_first_refresh()

    # Listen to config entry updates
    entry.async_on_unload(entry.add_update_listener(_async_signal_options_update))
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            _config_entry_update_signal_name(entry),
            coordinator.async_update_config,
        )
    )

    # Forward entry setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UpCloudConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
