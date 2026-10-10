"""The prowl component."""

import logging

import prowlpy

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN, SERVICE_NOTIFY
from homeassistant.config import config_per_platform
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.hass_dict import HassKey

from .const import CONF_ENTRY, CONF_LEGACY_SERVICE_NAME, CONF_NAMES, DOMAIN, PLATFORMS
from .helpers import async_verify_key

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

DATA_HASS_CONFIG: HassKey[ConfigType] = HassKey(f"{DOMAIN}_hass_config")
DATA_YAML_API_KEYS: HassKey[set[str]] = HassKey(f"{DOMAIN}_yaml_api_keys")
DATA_YAML_SERVICE_NAMES: HassKey[set[str]] = HassKey(f"{DOMAIN}_yaml_service_names")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Prowl component."""
    hass.data[DATA_HASS_CONFIG] = config
    yaml_configs = [
        p_config
        for platform, p_config in config_per_platform(config, NOTIFY_DOMAIN)
        if platform == DOMAIN and CONF_API_KEY in p_config
    ]
    # YAML names per API key, in YAML order, to import one entry per API key
    names_by_api_key: dict[str, list[str | None]] = {}
    for p_config in yaml_configs:
        names = names_by_api_key.setdefault(p_config[CONF_API_KEY], [])
        if (name := p_config.get(CONF_NAME)) not in names:
            names.append(name)
    hass.data[DATA_YAML_API_KEYS] = set(names_by_api_key)
    # Matches the service name the legacy notify loader uses for YAML platforms
    hass.data[DATA_YAML_SERVICE_NAMES] = {
        slugify(p_config.get(CONF_NAME) or SERVICE_NOTIFY) for p_config in yaml_configs
    }
    for api_key, names in names_by_api_key.items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_API_KEY: api_key, CONF_NAMES: names},
            )
        )
    if names_by_api_key:
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

    # A composed title (several YAML names) is not the legacy service name
    legacy_service_name = entry.data.get(CONF_LEGACY_SERVICE_NAME, entry.title)
    # While YAML for this API key or service name is present, YAML sets up the
    # legacy service
    if (
        entry.source == SOURCE_IMPORT
        and entry.data[CONF_API_KEY] not in hass.data[DATA_YAML_API_KEYS]
        and slugify(legacy_service_name) not in hass.data[DATA_YAML_SERVICE_NAMES]
    ):
        # Owned by the entry, so unloading cancels a pending setup
        entry.async_create_background_task(
            hass,
            discovery.async_load_platform(
                hass,
                Platform.NOTIFY,
                DOMAIN,
                {CONF_NAME: legacy_service_name, CONF_ENTRY: entry},
                hass.data[DATA_HASS_CONFIG],
            ),
            name=f"{DOMAIN} legacy notify setup",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
