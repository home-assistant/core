"""The Search integration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from enum import StrEnum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import automation, group, person, script, websocket_api
from homeassistant.components.homeassistant import scene
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity import (
    EntityInfo,
    entity_sources as get_entity_sources,
)
from homeassistant.helpers.typing import ConfigType

DOMAIN = "search"
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


# enum of item types
class ItemType(StrEnum):
    """Item types."""

    AREA = "area"
    AUTOMATION = "automation"
    AUTOMATION_BLUEPRINT = "automation_blueprint"
    CONFIG_ENTRY = "config_entry"
    DEVICE = "device"
    ENTITY = "entity"
    FLOOR = "floor"
    GROUP = "group"
    LABEL = "label"
    PERSON = "person"
    SCENE = "scene"
    SCRIPT = "script"
    SCRIPT_BLUEPRINT = "script_blueprint"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Search component."""
    websocket_api.async_register_command(hass, websocket_search_related)
    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "search/related",
        vol.Required("item_type"): vol.Coerce(ItemType),
        vol.Required("item_id"): str,
    }
)
@callback
def websocket_search_related(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle search."""
    searcher = Searcher(hass, get_entity_sources(hass))
    connection.send_result(
        msg["id"], searcher.async_search(msg["item_type"], msg["item_id"])
    )


class Searcher:
    """Find related things."""

    EXIST_AS_ENTITY = {"automation", "group", "person", "scene", "script"}

    def __init__(
        self,
        hass: HomeAssistant,
        entity_sources: dict[str, EntityInfo],
    ) -> None:
        """Search results."""
        self.hass = hass
        self._area_registry = ar.async_get(hass)
        self._device_registry = dr.async_get(hass)
        self._entity_registry = er.async_get(hass)
        self._entity_sources = entity_sources
        self.results: defaultdict[ItemType, set[str]] = defaultdict(set)

    @callback
    def async_search(self, item_type: ItemType, item_id: str) -> dict[str, set[str]]:
        """Find results."""
        _LOGGER.debug("Searching for %s/%s", item_type, item_id)
        getattr(self, f"_async_search_{item_type}")(item_id)

        # Remove the original requested item from the results (if present)
        if item_type in self.results and item_id in self.results[item_type]:
            self.results[item_type].remove(item_id)

        # Filter out empty sets.
        return {key: val for key, val in self.results.items() if val}

    @callback
    def _add(self, item_type: ItemType, item_id: str | Iterable[str] | None) -> None:
        """Add an item (or items) to the results."""
        if item_id is None:
            return

        if isinstance(item_id, str):
            self.results[item_type].add(item_id)
        else:
            self.results[item_type].update(item_id)

    @callback
    def _async_search_area(self, area_id: str, *, entry_point: bool = True) -> None:
        """Find results for an area."""
        if not (area_entry := self._async_resolve_up_area(area_id)):
            return

        if entry_point:
            # Add labels of this area
            self._add(ItemType.LABEL, area_entry.labels)

        # Automations referencing this area
        self._add(
            ItemType.AUTOMATION, automation.automations_with_area(self.hass, area_id)
        )

        # Scripts referencing this area
        self._add(ItemType.SCRIPT, script.scripts_with_area(self.hass, area_id))

        # Entity in this area, will extend this with the entities of the devices in this area
        entity_entries = er.async_entries_for_area(self._entity_registry, area_id)

        # Devices in this area
        for device in dr.async_entries_for_area(self._device_registry, area_id):
            self._add(ItemType.DEVICE, device.id)

            # Config entries for devices in this area
            if device_entry := self._device_registry.async_get(device.id):
                self._add(ItemType.CONFIG_ENTRY, device_entry.config_entries)

            # Automations referencing this device
            self._add(
                ItemType.AUTOMATION,
                automation.automations_with_device(self.hass, device.id),
            )

            # Scripts referencing this device
            self._add(ItemType.SCRIPT, script.scripts_with_device(self.hass, device.id))

            # Entities of this device
            for entity_entry in er.async_entries_for_device(
                self._entity_registry, device.id
            ):
                # Skip the entity if it's in a different area
                if entity_entry.area_id is not None:
                    continue
                entity_entries.append(entity_entry)

        # Process entities in this area
        for entity_entry in entity_entries:
            self._add(ItemType.ENTITY, entity_entry.entity_id)

            # If this entity also exists as a resource, we add it.
            if entity_entry.domain in self.EXIST_AS_ENTITY:
                self._add(ItemType(entity_entry.domain), entity_entry.entity_id)

            # Automations referencing this entity
            self._add(
                ItemType.AUTOMATION,
                automation.automations_with_entity(self.hass, entity_entry.entity_id),
            )

            # Scripts referencing this entity
            self._add(
                ItemType.SCRIPT,
                script.scripts_with_entity(self.hass, entity_entry.entity_id),
            )

            # Groups that have this entity as a member
            self._add(
                ItemType.GROUP,
                group.groups_with_entity(self.hass, entity_entry.entity_id),
            )

            # Persons that use this entity
            self._add(
                ItemType.PERSON,
                person.persons_with_entity(self.hass, entity_entry.entity_id),
            )

            # Scenes that reference this entity
            self._add(
                ItemType.SCENE,
                scene.scenes_with_entity(self.hass, entity_entry.entity_id),
            )

            # Config entries for entities in this area
            self._add(ItemType.CONFIG_ENTRY, entity_entry.config_entry_id)

    @callback
    def _async_search_automation(self, automation_entity_id: str) -> None:
        """Find results for an automation."""
        # Up resolve the automation entity itself
        if entity_entry := self._async_resolve_up_entity(automation_entity_id):
            # Add labels of this automation entity
            self._add(ItemType.LABEL, entity_entry.labels)

        # Find the blueprint used in this automation
        self._add(
            ItemType.AUTOMATION_BLUEPRINT,
            automation.blueprint_in_automation(self.hass, automation_entity_id),
        )

        # Floors referenced in this automation
        self._add(
            ItemType.FLOOR,
            automation.floors_in_automation(self.hass, automation_entity_id),
        )

        # Areas referenced in this automation
        for area in automation.areas_in_automation(self.hass, automation_entity_id):
            self._add(ItemType.AREA, area)
            self._async_resolve_up_area(area)

        # Devices referenced in this automation
        for device in automation.devices_in_automation(self.hass, automation_entity_id):
            self._add(ItemType.DEVICE, device)
            self._async_resolve_up_device(device)

        # Entities referenced in this automation
        for entity_id in automation.entities_in_automation(
            self.hass, automation_entity_id
        ):
            self._add(ItemType.ENTITY, entity_id)
            self._async_resolve_up_entity(entity_id)

            # If this entity also exists as a resource, we add it.
            domain = split_entity_id(entity_id)[0]
            if domain in self.EXIST_AS_ENTITY:
                self._add(ItemType(domain), entity_id)

            # For an automation, we want to unwrap the groups, to ensure we
            # relate this automation to all those members as well.
            if domain == "group":
                for group_entity_id in group.get_entity_ids(self.hass, entity_id):
                    self._add(ItemType.ENTITY, group_entity_id)
                    self._async_resolve_up_entity(group_entity_id)

            # For an automation, we want to unwrap the scenes, to ensure we
            # relate this automation to all referenced entities as well.
            if domain == "scene":
                for scene_entity_id in scene.entities_in_scene(self.hass, entity_id):
                    self._add(ItemType.ENTITY, scene_entity_id)
                    self._async_resolve_up_entity(scene_entity_id)

            # Fully search the script if it is part of an automation.
            # This makes the automation return all results of the embedded script.
            if domain == "script":
                self._async_search_script(entity_id, entry_point=False)

    @callback
    def _async_search_automation_blueprint(self, blueprint_path: str) -> None:
        """Find results for an automation blueprint."""
        self._add(
            ItemType.AUTOMATION,
            automation.automations_with_blueprint(self.hass, blueprint_path),
        )

    @callback
    def _async_search_config_entry(self, config_entry_id: str) -> None:
        """Find results for a config entry."""
        for device_entry in dr.async_entries_for_config_entry(
            self._device_registry, config_entry_id
        ):
            self._add(ItemType.DEVICE, device_entry.id)
            self._async_search_device(device_entry.id, entry_point=False)

        for entity_entry in er.async_entries_for_config_entry(
            self._entity_registry, config_entry_id
        ):
            self._add(ItemType.ENTITY, entity_entry.entity_id)
            self._async_search_entity(entity_entry.entity_id, entry_point=False)

    @callback
    def _async_search_device(self, device_id: str, *, entry_point: bool = True) -> None:
        """Find results for a device."""
        if not (device_entry := self._async_resolve_up_device(device_id)):
            return

        if entry_point:
            # Add labels of this device
            self._add(ItemType.LABEL, device_entry.labels)

        # Automations referencing this device
        self._add(
            ItemType.AUTOMATION,
            automation.automations_with_device(self.hass, device_id),
        )

        # Scripts referencing this device
        self._add(ItemType.SCRIPT, script.scripts_with_device(self.hass, device_id))

        # Entities of this device
        for entity_entry in er.async_entries_for_device(
            self._entity_registry, device_id
        ):
            self._add(ItemType.ENTITY, entity_entry.entity_id)
            # Add all entity information as well
            self._async_search_entity(entity_entry.entity_id, entry_point=False)

    @callback
    def _async_search_entity(self, entity_id: str, *, entry_point: bool = True) -> None:
        """Find results for an entity."""
        # Resolve up the entity itself
        entity_entry = self._async_resolve_up_entity(entity_id)

        if entity_entry and entry_point:
            # Add labels of this entity
            self._add(ItemType.LABEL, entity_entry.labels)

        # Automations referencing this entity
        self._add(
            ItemType.AUTOMATION,
            automation.automations_with_entity(self.hass, entity_id),
        )

        # Scripts referencing this entity
        self._add(ItemType.SCRIPT, script.scripts_with_entity(self.hass, entity_id))

        # Groups that have this entity as a member
        self._add(ItemType.GROUP, group.groups_with_entity(self.hass, entity_id))

        # Persons referencing this entity
        self._add(ItemType.PERSON, person.persons_with_entity(self.hass, entity_id))

        # Scenes referencing this entity
        self._add(ItemType.SCENE, scene.scenes_with_entity(self.hass, entity_id))

    @callback
    def _async_search_floor(self, floor_id: str) -> None:
        """Find results for a floor."""
        # Automations referencing this floor
        self._add(
            ItemType.AUTOMATION,
            automation.automations_with_floor(self.hass, floor_id),
        )

        # Scripts referencing this floor
        self._add(ItemType.SCRIPT, script.scripts_with_floor(self.hass, floor_id))

        for area_entry in ar.async_entries_for_floor(self._area_registry, floor_id):
            self._add(ItemType.AREA, area_entry.id)
            self._async_search_area(area_entry.id, entry_point=False)

    @callback
    def _async_search_group(self, group_entity_id: str) -> None:
        """Find results for a group.

        Note: We currently only support the classic groups, thus
        we don't look up the area/floor for a group entity.
        """
        # Automations referencing this group
        self._add(
            ItemType.AUTOMATION,
            automation.automations_with_entity(self.hass, group_entity_id),
        )

        # Scripts referencing this group
        self._add(
            ItemType.SCRIPT, script.scripts_with_entity(self.hass, group_entity_id)
        )

        # Scenes that reference this group
        self._add(ItemType.SCENE, scene.scenes_with_entity(self.hass, group_entity_id))

        # Entities in this group
        for entity_id in group.get_entity_ids(self.hass, group_entity_id):
            self._add(ItemType.ENTITY, entity_id)
            self._async_resolve_up_entity(entity_id)

    @callback
    def _async_search_label(self, label_id: str) -> None:
        """Find results for a label."""

        # Areas with this label
        for area_entry in ar.async_entries_for_label(self._area_registry, label_id):
            self._add(ItemType.AREA, area_entry.id)

        # Devices with this label
        for device in dr.async_entries_for_label(self._device_registry, label_id):
            self._add(ItemType.DEVICE, device.id)

        # Entities with this label
        for entity_entry in er.async_entries_for_label(self._entity_registry, label_id):
            self._add(ItemType.ENTITY, entity_entry.entity_id)

            # If this entity also exists as a resource, we add it.
            domain = split_entity_id(entity_entry.entity_id)[0]
            if domain in self.EXIST_AS_ENTITY:
                self._add(ItemType(domain), entity_entry.entity_id)

        # Automations referencing this label
        self._add(
            ItemType.AUTOMATION,
            automation.automations_with_label(self.hass, label_id),
        )

        # Scripts referencing this label
        self._add(ItemType.SCRIPT, script.scripts_with_label(self.hass, label_id))

    @callback
    def _async_search_person(self, person_entity_id: str) -> None:
        """Find results for a person."""
        # Up resolve the scene entity itself
        if entity_entry := self._async_resolve_up_entity(person_entity_id):
            # Add labels of this person entity
            self._add(ItemType.LABEL, entity_entry.labels)

        # Automations referencing this person
        self._add(
            ItemType.AUTOMATION,
            automation.automations_with_entity(self.hass, person_entity_id),
        )

        # Scripts referencing this person
        self._add(
            ItemType.SCRIPT, script.scripts_with_entity(self.hass, person_entity_id)
        )

        # Add all member entities of this person
        self._add(
            ItemType.ENTITY, person.entities_in_person(self.hass, person_entity_id)
        )

    @callback
    def _async_search_scene(self, scene_entity_id: str) -> None:
        """Find results for a scene."""
        # Up resolve the scene entity itself
        if entity_entry := self._async_resolve_up_entity(scene_entity_id):
            # Add labels of this scene entity
            self._add(ItemType.LABEL, entity_entry.labels)

        # Automations referencing this scene
        self._add(
            ItemType.AUTOMATION,
            automation.automations_with_entity(self.hass, scene_entity_id),
        )

        # Scripts referencing this scene
        self._add(
            ItemType.SCRIPT, script.scripts_with_entity(self.hass, scene_entity_id)
        )

        # Add all entities in this scene
        for entity in scene.entities_in_scene(self.hass, scene_entity_id):
            self._add(ItemType.ENTITY, entity)
            self._async_resolve_up_entity(entity)

    @callback
    def _async_search_script(
        self, script_entity_id: str, *, entry_point: bool = True
    ) -> None:
        """Find results for a script."""
        # Up resolve the script entity itself
        entity_entry = self._async_resolve_up_entity(script_entity_id)

        if entity_entry and entry_point:
            # Add labels of this script entity
            self._add(ItemType.LABEL, entity_entry.labels)

        # Find the blueprint used in this script
        self._add(
            ItemType.SCRIPT_BLUEPRINT,
            script.blueprint_in_script(self.hass, script_entity_id),
        )

        # Floors referenced in this script
        self._add(ItemType.FLOOR, script.floors_in_script(self.hass, script_entity_id))

        # Areas referenced in this script
        for area in script.areas_in_script(self.hass, script_entity_id):
            self._add(ItemType.AREA, area)
            self._async_resolve_up_area(area)

        # Devices referenced in this script
        for device in script.devices_in_script(self.hass, script_entity_id):
            self._add(ItemType.DEVICE, device)
            self._async_resolve_up_device(device)

        # Entities referenced in this script
        for entity_id in script.entities_in_script(self.hass, script_entity_id):
            self._add(ItemType.ENTITY, entity_id)
            self._async_resolve_up_entity(entity_id)

            # If this entity also exists as a resource, we add it.
            domain = split_entity_id(entity_id)[0]
            if domain in self.EXIST_AS_ENTITY:
                self._add(ItemType(domain), entity_id)

            # For an script, we want to unwrap the groups, to ensure we
            # relate this script to all those members as well.
            if domain == "group":
                for group_entity_id in group.get_entity_ids(self.hass, entity_id):
                    self._add(ItemType.ENTITY, group_entity_id)
                    self._async_resolve_up_entity(group_entity_id)

            # For an script, we want to unwrap the scenes, to ensure we
            # relate this script to all referenced entities as well.
            if domain == "scene":
                for scene_entity_id in scene.entities_in_scene(self.hass, entity_id):
                    self._add(ItemType.ENTITY, scene_entity_id)
                    self._async_resolve_up_entity(scene_entity_id)

            # Fully search the script if it is nested.
            # This makes the script return all results of the embedded script.
            if domain == "script":
                self._async_search_script(entity_id, entry_point=False)

    @callback
    def _async_search_script_blueprint(self, blueprint_path: str) -> None:
        """Find results for a script blueprint."""
        self._add(
            ItemType.SCRIPT, script.scripts_with_blueprint(self.hass, blueprint_path)
        )

    @callback
    def _async_resolve_up_device(self, device_id: str) -> dr.DeviceEntry | None:
        """Resolve up from a device.

        Above a device is an area or floor.
        Above a device is also the config entry.
        """
        if device_entry := self._device_registry.async_get(device_id):
            if device_entry.area_id:
                self._add(ItemType.AREA, device_entry.area_id)
                self._async_resolve_up_area(device_entry.area_id)

            self._add(ItemType.CONFIG_ENTRY, device_entry.config_entries)

        return device_entry

    @callback
    def _async_resolve_up_entity(self, entity_id: str) -> er.RegistryEntry | None:
        """Resolve up from an entity.

        Above an entity is a device, area or floor.
        Above an entity is also the config entry.
        """
        if entity_entry := self._entity_registry.async_get(entity_id):
            # Entity has an overridden area
            if entity_entry.area_id:
                self._add(ItemType.AREA, entity_entry.area_id)
                self._async_resolve_up_area(entity_entry.area_id)

            # Inherit area from device
            elif entity_entry.device_id and (
                device_entry := self._device_registry.async_get(entity_entry.device_id)
            ):
                if device_entry.area_id:
                    self._add(ItemType.AREA, device_entry.area_id)
                    self._async_resolve_up_area(device_entry.area_id)

            # Add device that provided this entity
            self._add(ItemType.DEVICE, entity_entry.device_id)

            # Add config entry that provided this entity
            self._add(ItemType.CONFIG_ENTRY, entity_entry.config_entry_id)
        elif source := self._entity_sources.get(entity_id):
            # Add config entry that provided this entity
            self._add(ItemType.CONFIG_ENTRY, source.get("config_entry"))

        return entity_entry

    @callback
    def _async_resolve_up_area(self, area_id: str) -> ar.AreaEntry | None:
        """Resolve up from an area.

        Above an area can be a floor.
        """
        if area_entry := self._area_registry.async_get_area(area_id):
            self._add(ItemType.FLOOR, area_entry.floor_id)

        return area_entry
