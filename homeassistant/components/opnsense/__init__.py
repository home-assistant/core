"""Support for OPNSense Routers."""
from dataclasses import dataclass
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACE, DEFAULT_NAME, DOMAIN
from .coordinator import OPNSenseUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACE, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
PLATFORMS = [Platform.DEVICE_TRACKER]


@dataclass(slots=True)
class OPNSenseDomainData:
    """Dataclass to store interface clients."""

    coordinators: dict[str, OPNSenseUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the opnsense component."""

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    conf[CONF_NAME] = DEFAULT_NAME
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "OPNSense",
        },
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OPNSense from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = OPNSenseDomainData(coordinators={})

    data: OPNSenseDomainData = hass.data[DOMAIN]

    coordinator = OPNSenseUpdateCoordinator(
        hass=hass,
        entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    data.coordinators[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # drop interfaces client for config entry
        hass.data[DOMAIN].coordinators.pop(entry.entry_id)

    return unload_ok
