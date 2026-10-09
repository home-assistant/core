"""Support for UpCloud."""

import logging

import requests.exceptions
import upcloud_api

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import UpCloudConfigEntry, UpCloudDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: UpCloudConfigEntry) -> bool:
    """Set up the UpCloud config entry."""

    manager = upcloud_api.CloudManager(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )

    try:
        await hass.async_add_executor_job(manager.authenticate)
    except upcloud_api.UpCloudAPIError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="authentication_failed",
        ) from err
    except requests.exceptions.RequestException as err:
        # pylint: disable-next=home-assistant-log-and-raise
        _LOGGER.exception("Failed to connect")
        raise ConfigEntryNotReady from err

    coordinator = UpCloudDataUpdateCoordinator(
        hass,
        config_entry=entry,
        cloud_manager=manager,
        username=entry.data[CONF_USERNAME],
    )
    entry.runtime_data = coordinator

    # Call the UpCloud API to refresh data
    await coordinator.async_config_entry_first_refresh()

    # Forward entry setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UpCloudConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
