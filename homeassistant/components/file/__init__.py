"""The file component."""

import os

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_FILE_PATH, CONF_FILENAME, CONF_PLATFORM, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR]

YAML_PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the file integration."""

    # The YAML config was imported with HA Core 2024.6.0 and will be removed with
    # HA Core 2024.12
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.12",
        is_fixable=False,
        issue_domain=DOMAIN,
        learn_more_url="https://www.home-assistant.io/integrations/file/",
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "File",
        },
    )
    if hass.config_entries.async_entries(DOMAIN):
        # We skip import in case we already have config entries
        return True

    # Prepare to import the YAML config into separate config entries
    config_data: dict[str, list[ConfigType]] = {
        domain: [item for item in config[domain] if item.pop(CONF_PLATFORM) == DOMAIN]
        for domain in config
        if domain in YAML_PLATFORMS
    }

    for domain, items in config_data.items():
        for item in items:
            item[CONF_PLATFORM] = domain
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=item,
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a file component entry."""
    config = dict(entry.data)
    filepath: str = ""
    if (platform := config[CONF_PLATFORM]) == Platform.NOTIFY:
        filepath = os.path.join(hass.config.config_dir, config[CONF_FILENAME])
    elif platform == Platform.SENSOR:
        filepath = config[CONF_FILE_PATH]
    if filepath and not await hass.async_add_executor_job(
        hass.config.is_allowed_path, filepath
    ):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="dir_not_allowed",
            translation_placeholders={"filename": filepath},
        )

    if entry.data[CONF_PLATFORM] in PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform(entry.data[CONF_PLATFORM])]
        )
    else:
        # The notify platform is not yet set up as entry, so
        # forward setup config through discovery to ensure setup notify service.
        # This is needed as long as the legacy service is not migrated
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                Platform.NOTIFY,
                DOMAIN,
                config,
                {},
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [entry.data[CONF_PLATFORM]]
    )
