"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import logging

from pyrainbird.async_client import AsyncRainbirdClient, AsyncRainbirdController
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TRIGGER_TIME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_CONFIG_ENTRY_ID, ATTR_DURATION, CONF_SERIAL_NUMBER, CONF_ZONES
from .coordinator import RainbirdUpdateCoordinator

PLATFORMS = [Platform.SWITCH, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rainbird"

TRIGGER_TIME_SCHEMA = vol.All(
    cv.time_period, cv.positive_timedelta, lambda td: (td.total_seconds() // 60)
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_TRIGGER_TIME): TRIGGER_TIME_SCHEMA,
    }
)
CONTROLLER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_TRIGGER_TIME): TRIGGER_TIME_SCHEMA,
        vol.Optional(CONF_ZONES): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [CONTROLLER_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SET_RAIN_DELAY = "set_rain_delay"
SERVICE_SCHEMA_RAIN_DELAY = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            vol.Required(ATTR_DURATION): cv.positive_float,
        }
    ),
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Rain Bird component."""
    if DOMAIN not in config:
        return True

    for controller_config in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=controller_config,
            )
        )

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.4.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the config entry for Rain Bird."""

    hass.data.setdefault(DOMAIN, {})

    controller = AsyncRainbirdController(
        AsyncRainbirdClient(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            entry.data[CONF_PASSWORD],
        )
    )
    coordinator = RainbirdUpdateCoordinator(
        hass,
        name=entry.title,
        controller=controller,
        serial_number=entry.data[CONF_SERIAL_NUMBER],
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def set_rain_delay(call: ServiceCall) -> None:
        """Service call to delay automatic irrigigation."""

        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        duration = call.data[ATTR_DURATION]
        if entry_id not in hass.data[DOMAIN]:
            raise HomeAssistantError(f"Config entry id does not exist: {entry_id}")
        coordinator = hass.data[DOMAIN][entry_id]

        entity_registry = er.async_get(hass)
        entity_ids = (
            entry.entity_id
            for entry in er.async_entries_for_config_entry(entity_registry, entry_id)
            if entry.unique_id == f"{coordinator.serial_number}-rain-delay"
        )
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_raindelay",
            breaks_in_ha_version="2023.4.0",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_raindelay",
            translation_placeholders={
                "alternate_target": next(entity_ids, "unknown"),
            },
        )

        await coordinator.controller.set_rain_delay(duration)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_RAIN_DELAY,
        set_rain_delay,
        schema=SERVICE_SCHEMA_RAIN_DELAY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        hass.services.async_remove(DOMAIN, SERVICE_SET_RAIN_DELAY)

    return unload_ok
