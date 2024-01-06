"""Support for testing internet speed via Fast.com."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, ServiceCall
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MANUAL, DEFAULT_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import FastdotcomDataUpdateCoordindator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
                vol.Optional(CONF_MANUAL, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Fast.com component. (deprecated)."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fast.com from a config entry."""
    coordinator = FastdotcomDataUpdateCoordindator(hass)

    async def _request_refresh(event: Event) -> None:
        """Request a refresh."""
        await coordinator.async_request_refresh()

    async def _request_refresh_service(call: ServiceCall) -> None:
        """Request a refresh via the service."""
        ir.async_create_issue(
            hass,
            DOMAIN,
            "service_deprecation",
            breaks_in_ha_version="2024.7.0",
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="service_deprecation",
        )
        await coordinator.async_request_refresh()

    if hass.state == CoreState.running:
        await coordinator.async_config_entry_first_refresh()
    else:
        # Don't start the speedtest when HA is starting up
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _request_refresh)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.services.async_register(DOMAIN, "speedtest", _request_refresh_service)

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Fast.com config entry."""
    hass.services.async_remove(DOMAIN, "speedtest")
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
