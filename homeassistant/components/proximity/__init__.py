"""Support for tracking the proximity of a device."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_TRACKED_ENTITIES, DOMAIN
from .coordinator import (
    TRACKED_ENTITY_REMOVED_ISSUE_PREFIX,
    ProximityConfigEntry,
    ProximityDataUpdateCoordinator,
    async_create_tracked_entity_removed_issue,
    tracked_entity_removed_issue_id,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@callback
def _async_migrate_tracked_entity_removed_issues(hass: HomeAssistant) -> None:
    """Migrate removed tracked entity issues to one issue per config entry."""
    issue_registry = ir.async_get(hass)
    # Issues created before they were per config entry are not linked to one
    legacy_issues = [
        issue
        for (domain, issue_id), issue in issue_registry.issues.items()
        if domain == DOMAIN
        and issue_id.startswith(TRACKED_ENTITY_REMOVED_ISSUE_PREFIX)
        and issue.config_entry_id is None
    ]
    for legacy_issue in legacy_issues:
        entity_id = legacy_issue.issue_id.removeprefix(
            TRACKED_ENTITY_REMOVED_ISSUE_PREFIX
        )
        for entry in hass.config_entries.async_entries(DOMAIN):
            # Entries are only migrated from data to options when set up, after this
            settings = {**entry.data, **entry.options}
            if entity_id not in settings[CONF_TRACKED_ENTITIES]:
                continue
            async_create_tracked_entity_removed_issue(hass, entry, entity_id)
            if legacy_issue.dismissed_version is not None:
                ir.async_ignore_issue(
                    hass,
                    DOMAIN,
                    tracked_entity_removed_issue_id(entry.entry_id, entity_id),
                    True,
                )
        ir.async_delete_issue(hass, DOMAIN, legacy_issue.issue_id)


@callback
def _async_delete_untracked_entity_removed_issues(
    hass: HomeAssistant, entry: ProximityConfigEntry
) -> None:
    """Delete removed tracked entity issues of entities no longer tracked."""
    issue_registry = ir.async_get(hass)
    tracked_issue_ids = {
        tracked_entity_removed_issue_id(entry.entry_id, entity_id)
        for entity_id in entry.options[CONF_TRACKED_ENTITIES]
    }
    prefix = tracked_entity_removed_issue_id(entry.entry_id, "")
    for domain, issue_id in list(issue_registry.issues):
        if (
            domain == DOMAIN
            and issue_id.startswith(prefix)
            and issue_id not in tracked_issue_ids
        ):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the proximity component."""
    _async_migrate_tracked_entity_removed_issues(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ProximityConfigEntry) -> None:
    """Migrate old entry."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry, data={}, options={**entry.data, **entry.options}, version=2
        )


async def async_setup_entry(hass: HomeAssistant, entry: ProximityConfigEntry) -> None:
    """Set up Proximity from a config entry."""
    _LOGGER.debug("setup %s with config:%s", entry.title, entry.options)

    _async_delete_untracked_entity_removed_issues(hass, entry)

    coordinator = ProximityDataUpdateCoordinator(hass, entry)

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            entry.options[CONF_TRACKED_ENTITIES],
            coordinator.async_check_proximity_state_change,
        )
    )

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass,
            entry.options[CONF_TRACKED_ENTITIES],
            coordinator.async_check_tracked_entity_change,
        )
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])


async def async_unload_entry(hass: HomeAssistant, entry: ProximityConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, [Platform.SENSOR])
