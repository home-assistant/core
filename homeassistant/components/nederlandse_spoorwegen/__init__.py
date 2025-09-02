"""The Nederlandse Spoorwegen integration."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import ConfigType

from .api import NSAPIWrapper
from .const import CONF_ROUTES, DOMAIN
from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

# Config schema for YAML configuration (legacy support)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_ROUTES, default=[]): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required("name"): cv.string,
                                vol.Required("from"): cv.string,
                                vol.Required("to"): cv.string,
                                vol.Optional("via"): cv.string,
                                vol.Optional("time"): cv.string,
                            }
                        )
                    ],
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nederlandse Spoorwegen component."""
    yaml_config_found = False
    platform_config_found = False

    # Check if integration-level YAML configuration exists
    if DOMAIN in config:
        yaml_config_found = True
        yaml_config = config[DOMAIN]

        # Issue a deprecation warning
        _LOGGER.warning(
            "Configuration of Nederlandse Spoorwegen integration via YAML is deprecated. "
            "Please remove the 'nederlandse_spoorwegen' configuration from your YAML "
            "configuration file and configure the integration via the UI instead"
        )

        # Always create a repair issue to notify the user when YAML config is present
        async_create_issue(
            hass,
            DOMAIN,
            "integration_yaml_migration",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="integration_yaml_migration",
        )

        # Check if config entry already exists (migration was already performed)
        existing_entries = hass.config_entries.async_entries(DOMAIN)
        if not existing_entries:
            # Only trigger import flow if no config entry exists yet
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data=yaml_config,
                )
            )

    # Check for platform-level configuration (legacy support)
    sensor_config = config.get("sensor", [])
    if isinstance(sensor_config, list):
        for sensor in sensor_config:
            if isinstance(sensor, dict) and sensor.get("platform") == DOMAIN:
                platform_config_found = True
                _LOGGER.warning(
                    "Platform-based configuration for Nederlandse Spoorwegen is deprecated. "
                    "Configuration will be automatically migrated to the new format"
                )

                # Always create a repair issue to notify the user when platform config is present
                _LOGGER.info("Creating repair issue for platform YAML migration")
                async_create_issue(
                    hass,
                    DOMAIN,
                    "platform_yaml_migration",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key="platform_yaml_migration",
                )
                _LOGGER.info("Repair issue created with ID: platform_yaml_migration")

                # Check if config entry already exists (migration was already performed)
                existing_entries = hass.config_entries.async_entries(DOMAIN)
                _LOGGER.info("Found %d existing config entries", len(existing_entries))
                if not existing_entries:
                    # Only trigger import flow if no config entry exists yet
                    # Extract platform configuration and convert to integration format
                    platform_data = {
                        CONF_API_KEY: sensor.get(CONF_API_KEY),
                        CONF_ROUTES: sensor.get(CONF_ROUTES, []),
                    }

                    # Trigger import flow for platform configuration
                    hass.async_create_task(
                        hass.config_entries.flow.async_init(
                            DOMAIN,
                            context={"source": "import"},
                            data=platform_data,
                        )
                    )
                break

    # Clean up migration issues if no YAML configuration exists
    _LOGGER.info(
        "Cleanup phase: yaml_config_found=%s, platform_config_found=%s",
        yaml_config_found,
        platform_config_found,
    )
    if not yaml_config_found:
        _LOGGER.info("Deleting integration_yaml_migration repair issue")
        async_delete_issue(hass, DOMAIN, "integration_yaml_migration")
    if not platform_config_found:
        _LOGGER.info("Deleting platform_yaml_migration repair issue")
        async_delete_issue(hass, DOMAIN, "platform_yaml_migration")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""
    api_wrapper = NSAPIWrapper(hass, entry.data[CONF_API_KEY])
    coordinator = NSDataUpdateCoordinator(hass, api_wrapper, entry)

    # Fetch initial data so we have data when the platforms setup
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator in the entry runtime data
    entry.runtime_data = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
