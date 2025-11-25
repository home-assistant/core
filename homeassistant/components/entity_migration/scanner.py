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
        """
        Scan Home Assistant configuration and dashboards for references to the given entity.
        
        Parameters:
            entity_id (str): The entity ID to locate (for example, "light.kitchen").
        
        Returns:
            ScanResult: Aggregated results containing `source_entity_id`, a mapping of config
            types to lists of `Reference` objects where the entity is used, and `total_count`
            of found references.
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
        """
        Finds automation configurations that reference the given entity.
        
        Returns:
            list[Reference]: A list of Reference objects for each automation/location where the entity is referenced (one entry per found location).
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
        """
        Identify locations within an automation where the given entity is referenced.
        
        Returns:
            locations (list[str]): List of location identifiers indicating where the entity is referenced
            within the automation. If the automation state is unavailable or no specific location can be
            determined, returns a list containing `LOCATION_ENTITY`.
        """
        locations: list[str] = []

        # Try to get the automation entity to access its config
        state = self.hass.states.get(automation_entity_id)
        if not state:
            return locations

        # Check trigger, condition, action attributes if available
        # The automation entity stores referenced entities in attributes
        attrs = state.attributes
        if "id" in attrs:
            # For UI automations, we can potentially get more detail
            # but for now, we return a generic location
            locations.append(LOCATION_ENTITY)
        else:
            locations.append(LOCATION_ENTITY)

        return locations if locations else [LOCATION_ENTITY]

    async def _async_scan_scripts(self, entity_id: str) -> list[Reference]:
        """
        Find scripts that reference the given entity and produce Reference entries for each match.
        
        Returns:
            refs (list[Reference]): A list of Reference objects for each script that references the entity. Each Reference uses CONFIG_TYPE_SCRIPT as the config_type, the script's unique id (or entity id) as config_id, the resolved display name as config_name, and LOCATION_SEQUENCE as the location.
        """
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
        """
        Finds scenes that reference the specified entity and returns references describing each match.
        
        Each Reference identifies the scene (using the scene's unique ID when available or the scene entity_id otherwise), a display name resolved from the entity registry or state, and marks the location as LOCATION_ENTITY.
        
        Returns:
            list[Reference]: A list of Reference objects for scenes that reference the given entity_id.
        """
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
        """
        Find group configurations that reference the given entity.
        
        Parameters:
            entity_id (str): The entity_id to search for within groups.
        
        Returns:
            list[Reference]: Reference entries for each group containing the entity. Each reference uses CONFIG_TYPE_GROUP, sets config_id to the group's unique id (or the group entity id if unavailable), config_name to the group's display name (or entity id), and location LOCATION_MEMBER.
        """
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
        """
        Find person entities that reference the given entity as a device tracker.
        
        Resolves each person's display name and unique id from the entity registry when available, falling back to the entity state or entity id.
        
        Returns:
            list[Reference]: References for matching person entities. Each Reference has
                config_type set to CONFIG_TYPE_PERSON, config_id set to the person's
                unique id or entity id, config_name set to the resolved display name,
                and location set to LOCATION_DEVICE_TRACKER.
        """
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
        """
        Scan Lovelace dashboards for references to the given entity.
        
        Scans every loaded Lovelace dashboard configuration, skipping dashboards without a config or those that fail to load, and records each location where the entity_id is referenced.
        
        Returns:
            refs (list[Reference]): A list of Reference objects describing each dashboard location where the entity is referenced. Returns an empty list if Lovelace is not loaded or no references are found.
        """
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
        """
        Recursively locate paths inside a configuration where the given entity_id is referenced.
        
        Parameters:
            config (Any): Configuration node to scan (dict, list, or value).
            entity_id (str): The entity ID to search for.
            path (str): Current traversal path using dot notation for dict keys and `[index]` for list items; used in reported locations.
        
        Returns:
            list[str]: Paths where the entity was found. Template-based matches are suffixed with " (template)".
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
        """
        Detects whether a Jinja2 template contains a reference to a specific entity.
        
        Parameters:
            template (str): Jinja2 template text to inspect.
            entity_id (str): The entity_id to search for within the template.
        
        Returns:
            `true` if the `entity_id` is referenced in the template, `false` otherwise.
        """
        for pattern in TEMPLATE_PATTERNS:
            matches = pattern.findall(template)
            if entity_id in matches:
                return True
        return False