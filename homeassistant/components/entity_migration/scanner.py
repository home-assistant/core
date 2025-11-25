"""Entity reference scanner for the Entity Migration integration."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components import automation, group, person, script
from homeassistant.components.homeassistant import scene
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONFIG_TYPE_AUTOMATION,
    CONFIG_TYPE_DASHBOARD,
    CONFIG_TYPE_GROUP,
    CONFIG_TYPE_PERSON,
    CONFIG_TYPE_SCENE,
    CONFIG_TYPE_SCRIPT,
    LOCATION_DEVICE_TRACKER,
    LOCATION_ENTITY,
    LOCATION_MEMBER,
    LOCATION_SEQUENCE,
)
from .models import Reference, ScanResult

if TYPE_CHECKING:
    from homeassistant.components.lovelace import LovelaceData

_LOGGER = logging.getLogger(__name__)

# Regex patterns for Jinja2 template detection
# Matches: states('entity_id'), states.entity_id, is_state('entity_id', ...),
# state_attr('entity_id', ...), etc.
TEMPLATE_PATTERNS = [
    re.compile(r"states\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    re.compile(r"states\.([a-z_]+\.[a-z0-9_]+)"),
    re.compile(r"is_state\s*\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"state_attr\s*\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"is_state_attr\s*\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"expand\s*\(\s*['\"]([^'\"]+)['\"]"),
]


class EntityMigrationScanner:
    """Scan for entity references across Home Assistant configurations."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the scanner."""
        self.hass = hass

    async def async_scan(self, entity_id: str) -> ScanResult:
        """Find all references to an entity across all configuration types.

        Args:
            entity_id: The entity ID to scan for references.

        Returns:
            ScanResult containing all found references grouped by config type.
        """
        _LOGGER.debug("Starting scan for entity %s", entity_id)

        # Run all scans in parallel for performance
        results = await asyncio.gather(
            self._async_scan_automations(entity_id),
            self._async_scan_scripts(entity_id),
            self._async_scan_scenes(entity_id),
            self._async_scan_groups(entity_id),
            self._async_scan_persons(entity_id),
            self._async_scan_dashboards(entity_id),
            return_exceptions=True,
        )

        references: dict[str, list[Reference]] = {}
        total_count = 0

        # Process results, handling any exceptions gracefully
        scan_types = [
            CONFIG_TYPE_AUTOMATION,
            CONFIG_TYPE_SCRIPT,
            CONFIG_TYPE_SCENE,
            CONFIG_TYPE_GROUP,
            CONFIG_TYPE_PERSON,
            CONFIG_TYPE_DASHBOARD,
        ]

        for scan_type, result in zip(scan_types, results, strict=True):
            if isinstance(result, BaseException):
                _LOGGER.warning(
                    "Error scanning %s: %s", scan_type, result
                )
                continue
            # At this point, result is list[Reference]
            refs: list[Reference] = result
            if refs:
                references[scan_type] = refs
                total_count += len(refs)

        scan_result = ScanResult(
            source_entity_id=entity_id,
            references=references,
            total_count=total_count,
        )

        _LOGGER.debug(
            "Scan complete for %s: %d total references found",
            entity_id,
            total_count,
        )

        return scan_result

    async def _async_scan_automations(self, entity_id: str) -> list[Reference]:
        """Scan automations for entity references.

        Uses the built-in automations_with_entity() helper and then retrieves
        additional location information.
        """
        refs: list[Reference] = []

        # Get all automations that reference this entity
        automation_ids = automation.automations_with_entity(self.hass, entity_id)

        entity_registry = er.async_get(self.hass)

        for auto_entity_id in automation_ids:
            # Get automation name from entity registry or state
            entry = entity_registry.async_get(auto_entity_id)
            if entry:
                name = entry.name or entry.original_name or auto_entity_id
                auto_id = entry.unique_id or auto_entity_id
            else:
                state = self.hass.states.get(auto_entity_id)
                name = state.name if state else auto_entity_id
                auto_id = auto_entity_id

            # Determine location within automation by inspecting config
            locations = await self._get_automation_locations(auto_entity_id, entity_id)

            refs.extend(
                Reference(
                    config_type=CONFIG_TYPE_AUTOMATION,
                    config_id=auto_id,
                    config_name=name,
                    location=location,
                )
                for location in locations or [LOCATION_ENTITY]
            )

        return refs

    async def _get_automation_locations(
        self, automation_entity_id: str, entity_id: str
    ) -> list[str]:
        """Determine where in an automation an entity is referenced."""
        locations: list[str] = []

        # Try to get the automation entity to access its config
        state = self.hass.states.get(automation_entity_id)
        if not state:
            return locations

        # The automation entity stores referenced entities in attributes
        # For now, return a generic location; future enhancement could
        # distinguish trigger/condition/action based on automation config
        locations.append(LOCATION_ENTITY)

        return locations

    async def _async_scan_scripts(self, entity_id: str) -> list[Reference]:
        """Scan scripts for entity references."""
        refs: list[Reference] = []

        script_ids = script.scripts_with_entity(self.hass, entity_id)
        entity_registry = er.async_get(self.hass)

        for script_entity_id in script_ids:
            entry = entity_registry.async_get(script_entity_id)
            if entry:
                name = entry.name or entry.original_name or script_entity_id
                script_id = entry.unique_id or script_entity_id
            else:
                state = self.hass.states.get(script_entity_id)
                name = state.name if state else script_entity_id
                script_id = script_entity_id

            refs.append(
                Reference(
                    config_type=CONFIG_TYPE_SCRIPT,
                    config_id=script_id,
                    config_name=name,
                    location=LOCATION_SEQUENCE,
                )
            )

        return refs

    async def _async_scan_scenes(self, entity_id: str) -> list[Reference]:
        """Scan scenes for entity references."""
        refs: list[Reference] = []

        scene_ids = scene.scenes_with_entity(self.hass, entity_id)
        entity_registry = er.async_get(self.hass)

        for scene_entity_id in scene_ids:
            entry = entity_registry.async_get(scene_entity_id)
            if entry:
                name = entry.name or entry.original_name or scene_entity_id
                scene_id = entry.unique_id or scene_entity_id
            else:
                state = self.hass.states.get(scene_entity_id)
                name = state.name if state else scene_entity_id
                scene_id = scene_entity_id

            refs.append(
                Reference(
                    config_type=CONFIG_TYPE_SCENE,
                    config_id=scene_id,
                    config_name=name,
                    location=LOCATION_ENTITY,
                )
            )

        return refs

    async def _async_scan_groups(self, entity_id: str) -> list[Reference]:
        """Scan groups for entity references."""
        refs: list[Reference] = []

        group_ids = group.groups_with_entity(self.hass, entity_id)
        entity_registry = er.async_get(self.hass)

        for group_entity_id in group_ids:
            entry = entity_registry.async_get(group_entity_id)
            if entry:
                name = entry.name or entry.original_name or group_entity_id
                grp_id = entry.unique_id or group_entity_id
            else:
                state = self.hass.states.get(group_entity_id)
                name = state.name if state else group_entity_id
                grp_id = group_entity_id

            refs.append(
                Reference(
                    config_type=CONFIG_TYPE_GROUP,
                    config_id=grp_id,
                    config_name=name,
                    location=LOCATION_MEMBER,
                )
            )

        return refs

    async def _async_scan_persons(self, entity_id: str) -> list[Reference]:
        """Scan person entities for device_tracker references."""
        refs: list[Reference] = []

        person_ids = person.persons_with_entity(self.hass, entity_id)
        entity_registry = er.async_get(self.hass)

        for person_entity_id in person_ids:
            entry = entity_registry.async_get(person_entity_id)
            if entry:
                name = entry.name or entry.original_name or person_entity_id
                person_id = entry.unique_id or person_entity_id
            else:
                state = self.hass.states.get(person_entity_id)
                name = state.name if state else person_entity_id
                person_id = person_entity_id

            refs.append(
                Reference(
                    config_type=CONFIG_TYPE_PERSON,
                    config_id=person_id,
                    config_name=name,
                    location=LOCATION_DEVICE_TRACKER,
                )
            )

        return refs

    async def _async_scan_dashboards(self, entity_id: str) -> list[Reference]:
        """Scan Lovelace dashboards for entity references."""
        refs: list[Reference] = []

        if LOVELACE_DATA not in self.hass.data:
            _LOGGER.debug("Lovelace not loaded, skipping dashboard scan")
            return refs

        lovelace_data: LovelaceData = self.hass.data[LOVELACE_DATA]

        # Scan all dashboards (None is the default dashboard)
        for url_path, dashboard_config in lovelace_data.dashboards.items():
            try:
                config = await dashboard_config.async_load(force=False)
            except ConfigNotFound:
                _LOGGER.debug(
                    "Dashboard %s has no config, skipping",
                    url_path or "default",
                )
                continue
            except (OSError, ValueError) as err:
                _LOGGER.warning(
                    "Error loading dashboard %s, skipping: %s",
                    url_path or "default",
                    err,
                )
                continue

            dashboard_name = url_path or "Overview"
            dashboard_id = url_path or "lovelace"

            # Deep scan the config for entity references
            found_locations = self._deep_scan_config(config, entity_id)

            refs.extend(
                Reference(
                    config_type=CONFIG_TYPE_DASHBOARD,
                    config_id=dashboard_id,
                    config_name=dashboard_name,
                    location=location,
                )
                for location in found_locations
            )

        return refs

    @callback
    def _deep_scan_config(
        self,
        config: Any,
        entity_id: str,
        path: str = "",
    ) -> list[str]:
        """Recursively scan a configuration for entity references.

        Args:
            config: The configuration to scan (dict, list, or value).
            entity_id: The entity ID to search for.
            path: Current path in the config for location reporting.

        Returns:
            List of paths where the entity was found.
        """
        found: list[str] = []

        if isinstance(config, dict):
            for key, value in config.items():
                new_path = f"{path}.{key}" if path else key
                found.extend(self._deep_scan_config(value, entity_id, new_path))

        elif isinstance(config, list):
            for idx, item in enumerate(config):
                new_path = f"{path}[{idx}]"
                found.extend(self._deep_scan_config(item, entity_id, new_path))

        elif isinstance(config, str):
            # Check for direct entity ID match or entity in comma-separated list
            if config == entity_id or entity_id in config.split(","):
                found.append(path)
            # Check for Jinja2 template references
            elif ("{{" in config or "{%" in config) and self._check_template_reference(
                config, entity_id
            ):
                found.append(f"{path} (template)")

        return found

    @callback
    def _check_template_reference(self, template: str, entity_id: str) -> bool:
        """Check if a Jinja2 template contains a reference to an entity."""
        for pattern in TEMPLATE_PATTERNS:
            matches = pattern.findall(template)
            if entity_id in matches:
                return True
        return False
