"""Dreo for Integration."""

from dataclasses import dataclass
import logging
from typing import Any

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

type DreoConfigEntry = ConfigEntry[DreoData]

# Add more platforms as they become supported
PLATFORMS = [Platform.FAN]

_LOGGER = logging.getLogger(__name__)


@dataclass
class DreoData:
    """Dreo Data."""

    client: HsCloud
    devices: list[dict[str, Any]]


async def async_login(hass: HomeAssistant, username: str, password: str) -> DreoData:
    """Log into Dreo and return client and device data."""
    client = HsCloud(username, password)

    def setup_client():
        client.login()
        return client.get_devices()

    try:
        devices = await hass.async_add_executor_job(setup_client)
    except HsCloudException as ex:
        _LOGGER.exception("Unable to connect")
        raise ConfigEntryNotReady("unable to connect") from ex
    except HsCloudBusinessException as ex:
        _LOGGER.exception("Invalid username or password")
        raise ConfigEntryNotReady("invalid username or password") from ex

    return DreoData(client, devices)


async def async_setup_entry(hass: HomeAssistant, config_entry: DreoConfigEntry) -> bool:
    """Set up Dreo from as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    hass.data.setdefault(DOMAIN, {})

    # Login and get device data
    config_entry.runtime_data = await async_login(hass, username, password)

    # Store in hass.data for access by platforms
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.runtime_data

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
