"""The prowl component."""

import logging

import prowlpy

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config import config_per_platform
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import CONF_ENTRY, DOMAIN, PLATFORMS
from .helpers import async_verify_key

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

DATA_YAML_API_KEYS: HassKey[set[str]] = HassKey(f"{DOMAIN}_yaml_api_keys")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Prowl component."""
    hass.data[DATA_YAML_API_KEYS] = {
        p_config[CONF_API_KEY]
        for platform, p_config in config_per_platform(config, NOTIFY_DOMAIN)
        if platform == DOMAIN and CONF_API_KEY in p_config
    }
    if hass.data[DATA_YAML_API_KEYS]:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2027.5.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={"domain": DOMAIN, "integration_title": "Prowl"},
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Prowl service."""
    yaml_api_keys = hass.data[DATA_YAML_API_KEYS]

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

    # While YAML for this API key is present, YAML sets up the legacy service
    if entry.source == SOURCE_IMPORT and entry.data[CONF_API_KEY] not in yaml_api_keys:
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                Platform.NOTIFY,
                DOMAIN,
                {CONF_NAME: entry.title, CONF_ENTRY: entry},
                {},
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
