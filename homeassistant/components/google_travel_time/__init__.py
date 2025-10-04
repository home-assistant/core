"""The google_travel_time component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util import dt as dt_util

from .config_flow import GoogleTravelTimeConfigFlow
from .const import ATTR_DURATION, CONF_TIME, DOMAIN

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Maps Travel Time from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""

    if config_entry.version != GoogleTravelTimeConfigFlow.VERSION:
        _LOGGER.debug(
            "Migrating from version %s.%s",
            config_entry.version,
            config_entry.minor_version,
        )

    if config_entry.version == 1:
        options = dict(config_entry.options)
        if options.get(CONF_TIME) == "now":
            options[CONF_TIME] = None
        elif options.get(CONF_TIME) is not None:
            if dt_util.parse_time(options[CONF_TIME]) is None:
                try:
                    from_timestamp = dt_util.utc_from_timestamp(int(options[CONF_TIME]))
                    options[CONF_TIME] = (
                        f"{from_timestamp.time().hour:02}:{from_timestamp.time().minute:02}"
                    )
                except ValueError:
                    _LOGGER.error(
                        "Invalid time format found while migrating: %s. The old config never worked. Reset to default (empty)",
                        options[CONF_TIME],
                    )
                    options[CONF_TIME] = None
        hass.config_entries.async_update_entry(config_entry, options=options, version=2)
    if config_entry.version == 2:
        entity_registry = er.async_get(hass)
        old_unique_id = config_entry.entry_id
        new_unique_id = f"{config_entry.entry_id}_{ATTR_DURATION}"

        if old_entity_id := entity_registry.async_get_entity_id(
            "sensor", DOMAIN, old_unique_id
        ):
            new_entity_id = f"{old_entity_id}_{ATTR_DURATION}"

            _LOGGER.debug(
                "Migrating unique_id from '%s' to '%s' and entity_id from '%s' to '%s'",
                old_unique_id,
                new_unique_id,
                old_entity_id,
                new_entity_id,
            )
            entity_registry.async_update_entity(
                old_entity_id,
                new_entity_id=new_entity_id,
                new_unique_id=new_unique_id,
            )
            async_create_issue(
                hass,
                DOMAIN,
                f"google_travel_time_unique_id_migration_{config_entry.entry_id}",
                is_fixable=False,
                is_persistent=True,
                severity=IssueSeverity.WARNING,
                translation_key="unique_id_migration",
                translation_placeholders={
                    "old_entity_id": old_entity_id,
                    "new_entity_id": new_entity_id,
                },
            )
        hass.config_entries.async_update_entry(config_entry, version=3)

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
