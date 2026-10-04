"""The prowl component."""

import logging

import prowlpy

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config import config_per_platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import CONF_ENTRY, CONF_LEGACY_SERVICE_NAME, DOMAIN, PLATFORMS
from .helpers import async_verify_key
from .issue import async_create_yaml_deprecated_issue

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

DATA_YAML_CONFIGURED: HassKey[bool] = HassKey(f"{DOMAIN}_yaml_configured")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Prowl component."""
    hass.data[DATA_YAML_CONFIGURED] = any(
        platform == DOMAIN for platform, _ in config_per_platform(config, NOTIFY_DOMAIN)
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Prowl service."""
    if hass.data[DATA_YAML_CONFIGURED]:
        async_create_yaml_deprecated_issue(hass)

    try:
        if not await async_verify_key(hass, entry.data[CONF_API_KEY]):
            raise ConfigEntryError(
                "Unable to validate Prowl API key (Key invalid or expired)"
            )
    except TimeoutError as ex:
        raise ConfigEntryNotReady("API call to Prowl failed") from ex
    except prowlpy.APIError as ex:
        if str(ex).startswith("Not accepted: exceeded rate limit"):
            raise ConfigEntryNotReady("Prowl API rate limit exceeded") from ex
        raise ConfigEntryError(f"Failed to validate Prowl API key ({ex})") from ex

    if CONF_LEGACY_SERVICE_NAME in entry.data:
        # Not awaited: the notify setup may be waiting on the YAML import of this entry
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                Platform.NOTIFY,
                DOMAIN,
                {CONF_NAME: entry.data[CONF_LEGACY_SERVICE_NAME], CONF_ENTRY: entry},
                {},
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
