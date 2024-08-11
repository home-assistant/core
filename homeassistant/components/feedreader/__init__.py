"""Support for RSS/Atom feeds."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_URL, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import CONF_MAX_ENTRIES, DEFAULT_MAX_ENTRIES, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import FeedReaderCoordinator, StoredData

type FeedReaderConfigEntry = ConfigEntry[FeedReaderCoordinator]

CONF_URLS = "urls"

MY_KEY: HassKey[StoredData] = HassKey(DOMAIN)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_URLS): vol.All(cv.ensure_list, [cv.url]),
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): cv.time_period,
                    vol.Optional(
                        CONF_MAX_ENTRIES, default=DEFAULT_MAX_ENTRIES
                    ): cv.positive_int,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Feedreader component."""
    if DOMAIN in config:
        for url in config[DOMAIN][CONF_URLS]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_URL: url,
                        CONF_MAX_ENTRIES: config[DOMAIN][CONF_MAX_ENTRIES],
                    },
                )
            )

        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2025.1.0",
            is_fixable=False,
            is_persistent=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Feedreader",
            },
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: FeedReaderConfigEntry) -> bool:
    """Set up Feedreader from a config entry."""
    storage = hass.data.setdefault(MY_KEY, StoredData(hass))
    if not storage.is_initialized:
        await storage.async_setup()

    coordinator = FeedReaderCoordinator(
        hass,
        entry.data[CONF_URL],
        entry.options[CONF_MAX_ENTRIES],
        storage,
    )

    await coordinator.async_setup()

    entry.runtime_data = coordinator

    # we need to setup event entities before the first coordinator data fetch
    # so that the event entities can already fetch the events during the first fetch
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.EVENT])

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FeedReaderConfigEntry) -> bool:
    """Unload a config entry."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )
    # if this is the last entry, remove the storage
    if len(entries) == 1:
        hass.data.pop(MY_KEY)
    return await hass.config_entries.async_unload_platforms(entry, Platform.EVENT)


async def _async_update_listener(
    hass: HomeAssistant, entry: FeedReaderConfigEntry
) -> None:
    """Handle reconfiguration."""
    await hass.config_entries.async_reload(entry.entry_id)
