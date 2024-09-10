"""The file component."""

from copy import deepcopy
from typing import Any

from homeassistant.components.notify import migrate_notify_issue
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_FILE_PATH,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_SCAN_INTERVAL,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .notify import PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA
from .sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA

IMPORT_SCHEMA = {
    Platform.SENSOR: SENSOR_PLATFORM_SCHEMA,
    Platform.NOTIFY: NOTIFY_PLATFORM_SCHEMA,
}

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the file integration."""

    hass.data[DOMAIN] = config
    if hass.config_entries.async_entries(DOMAIN):
        # We skip import in case we already have config entries
        return True
    # The use of the legacy notify service was deprecated with HA Core 2024.6.0
    # and will be removed with HA Core 2024.12
    migrate_notify_issue(hass, DOMAIN, "File", "2024.12.0")
    # The YAML config was imported with HA Core 2024.6.0 and will be removed with
    # HA Core 2024.12
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.12.0",
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

    # Import the YAML config into separate config entries
    platforms_config: dict[Platform, list[ConfigType]] = {
        domain: config[domain] for domain in PLATFORMS if domain in config
    }
    for domain, items in platforms_config.items():
        for item in items:
            if item[CONF_PLATFORM] == DOMAIN:
                file_config_item = IMPORT_SCHEMA[domain](item)
                file_config_item[CONF_PLATFORM] = domain
                if CONF_SCAN_INTERVAL in file_config_item:
                    del file_config_item[CONF_SCAN_INTERVAL]
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_IMPORT},
                        data=file_config_item,
                    )
                )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a file component entry."""
    config = {**entry.data, **entry.options}
    filepath: str = config[CONF_FILE_PATH]
    if filepath and not await hass.async_add_executor_job(
        hass.config.is_allowed_path, filepath
    ):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="dir_not_allowed",
            translation_placeholders={"filename": filepath},
        )

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(entry.data[CONF_PLATFORM])]
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))
    if entry.data[CONF_PLATFORM] == Platform.NOTIFY and CONF_NAME in entry.data:
        # New notify entities are being setup through the config entry,
        # but during the deprecation period we want to keep the legacy notify platform,
        # so we forward the setup config through discovery.
        # Only the entities from yaml will still be available as legacy service.
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                Platform.NOTIFY,
                DOMAIN,
                config,
                hass.data[DOMAIN],
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [entry.data[CONF_PLATFORM]]
    )


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry."""
    if config_entry.version > 2:
        # Downgraded from future
        return False

    if config_entry.version < 2:
        # Move optional fields from data to options in config entry
        data: dict[str, Any] = deepcopy(dict(config_entry.data))
        options = {}
        for key, value in config_entry.data.items():
            if key not in (CONF_FILE_PATH, CONF_PLATFORM, CONF_NAME):
                data.pop(key)
                options[key] = value

        hass.config_entries.async_update_entry(
            config_entry, version=2, data=data, options=options
        )
    return True
