"""Dreo for Integration."""

from dataclasses import dataclass
import logging

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS

_LOGGER = logging.getLogger(__name__)

type DreoConfigEntry = ConfigEntry[DreoData]


@dataclass
class DreoData:
    """Dreo Data."""

    client: HsCloud
    devices: list


async def async_setup_entry(hass: HomeAssistant, config_entry: DreoConfigEntry) -> bool:
    """Set up Dreo from as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    manager = HsCloud(username, password)
    try:
        await hass.async_add_executor_job(manager.login)
        config_entry.runtime_data = DreoData(
            manager, await hass.async_add_executor_job(manager.get_devices)
        )

    except HsCloudException as ex:
        _LOGGER.exception("Unable to connect")
        raise ConfigEntryNotReady("unable to connect") from ex

    except HsCloudBusinessException as ex:
        _LOGGER.exception("Invalid username or password")
        raise ConfigEntryNotReady("invalid username or password") from ex

    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        raise ConfigEntryNotReady("Unexpected exception") from ex

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
