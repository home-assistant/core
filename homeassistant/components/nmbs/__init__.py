"""The NMBS component."""

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PLATFORM, CONF_SHOW_ON_MAP, CONF_TYPE, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import CONF_EXCLUDE_VIAS, CONF_STATION_LIVE, DOMAIN  # noqa: F401

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NMBS component through yaml (deprecated)."""

    platforms_config: dict[Platform, list[ConfigType]] = {
        domain: config[domain] for domain in PLATFORMS if domain in config
    }
    for items in platforms_config.values():
        for item in items:
            if item[CONF_PLATFORM] == DOMAIN:
                if CONF_SHOW_ON_MAP not in item:
                    item[CONF_SHOW_ON_MAP] = False
                if CONF_EXCLUDE_VIAS not in item:
                    item[CONF_EXCLUDE_VIAS] = False

                item[CONF_TYPE] = "connection"
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_IMPORT},
                        data=item,
                    )
                )
                if CONF_STATION_LIVE in item:
                    liveboard = item.copy()
                    liveboard[CONF_TYPE] = "liveboard"
                    hass.async_create_task(
                        hass.config_entries.flow.async_init(
                            DOMAIN,
                            context={"source": SOURCE_IMPORT},
                            data=liveboard,
                        )
                    )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.3.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "NMBS",
        },
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NMBS from a config entry."""

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
