"""Support for scripts."""

from functools import partial
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.const import CONF_MODE, STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_registry import (
    EVENT_ENTITY_REGISTRY_UPDATED,
    EventEntityRegistryUpdatedData,
)
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.script import entity_id_in_config
from homeassistant.helpers.typing import ConfigType

from .config import ScriptConfig
from .const import ATTR_LAST_TRIGGERED, DOMAIN, EVENT_SCRIPT_STARTED, LOGGER
from .entity import BaseScriptEntity, UnavailableScriptEntity
from .helpers import async_get_blueprints
from .services import async_setup_services
from .util import async_process_config

__all__ = [
    "ATTR_LAST_TRIGGERED",
    "CONF_MODE",
    "DOMAIN",
    "EVENT_SCRIPT_STARTED",
    "BaseScriptEntity",
    "ScriptConfig",
    "UnavailableScriptEntity",
    "areas_in_script",
    "async_get_blueprints",
    "blueprint_in_script",
    "devices_in_script",
    "entities_in_script",
    "floors_in_script",
    "labels_in_script",
    "scripts_with_area",
    "scripts_with_blueprint",
    "scripts_with_device",
    "scripts_with_entity",
    "scripts_with_floor",
    "scripts_with_label",
]


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the script is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


def _scripts_with_x(
    hass: HomeAssistant, referenced_id: str, property_name: str
) -> list[str]:
    """Return all scripts that reference the x."""
    if DOMAIN not in hass.data:
        return []

    component: EntityComponent[BaseScriptEntity] = hass.data[DOMAIN]

    return [
        script_entity.entity_id
        for script_entity in component.entities
        if referenced_id in getattr(script_entity, property_name)
    ]


def _x_in_script(hass: HomeAssistant, entity_id: str, property_name: str) -> list[str]:
    """Return all x in a script."""
    if DOMAIN not in hass.data:
        return []

    component: EntityComponent[BaseScriptEntity] = hass.data[DOMAIN]

    if (script_entity := component.get_entity(entity_id)) is None:
        return []

    return list(getattr(script_entity, property_name))


@callback
def scripts_with_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all scripts that reference the entity."""
    return _scripts_with_x(hass, entity_id, "referenced_entities")


@callback
def entities_in_script(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all entities in script."""
    return _x_in_script(hass, entity_id, "referenced_entities")


@callback
def scripts_with_device(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return all scripts that reference the device."""
    return _scripts_with_x(hass, device_id, "referenced_devices")


@callback
def devices_in_script(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all devices in script."""
    return _x_in_script(hass, entity_id, "referenced_devices")


@callback
def scripts_with_area(hass: HomeAssistant, area_id: str) -> list[str]:
    """Return all scripts that reference the area."""
    return _scripts_with_x(hass, area_id, "referenced_areas")


@callback
def areas_in_script(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all areas in a script."""
    return _x_in_script(hass, entity_id, "referenced_areas")


@callback
def scripts_with_floor(hass: HomeAssistant, floor_id: str) -> list[str]:
    """Return all scripts that reference the floor."""
    return _scripts_with_x(hass, floor_id, "referenced_floors")


@callback
def floors_in_script(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all floors in a script."""
    return _x_in_script(hass, entity_id, "referenced_floors")


@callback
def scripts_with_label(hass: HomeAssistant, label_id: str) -> list[str]:
    """Return all scripts that reference the label."""
    return _scripts_with_x(hass, label_id, "referenced_labels")


@callback
def labels_in_script(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all labels in a script."""
    return _x_in_script(hass, entity_id, "referenced_labels")


@callback
def scripts_with_blueprint(hass: HomeAssistant, blueprint_path: str) -> list[str]:
    """Return all scripts that reference the blueprint."""
    if DOMAIN not in hass.data:
        return []

    component: EntityComponent[BaseScriptEntity] = hass.data[DOMAIN]

    return [
        script_entity.entity_id
        for script_entity in component.entities
        if script_entity.referenced_blueprint == blueprint_path
    ]


@callback
def blueprint_in_script(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the blueprint the script is based on or None."""
    if DOMAIN not in hass.data:
        return None

    component: EntityComponent[BaseScriptEntity] = hass.data[DOMAIN]

    if (script_entity := component.get_entity(entity_id)) is None:
        return None

    return script_entity.referenced_blueprint


@callback
def _async_entity_renamed_issues(
    hass: HomeAssistant, event: Event[EventEntityRegistryUpdatedData]
) -> None:
    """Create fixable issues for scripts referencing a renamed entity."""
    if event.data["action"] != "update" or not (
        old_entity_id := event.data.get("old_entity_id")
    ):
        return
    new_entity_id = event.data["entity_id"]
    issue_registry = ir.async_get(hass)

    # Retarget pending issues when the entity is renamed again, and remove
    # them when the referenced ID becomes valid once more.
    for (issue_domain, issue_id), issue in tuple(issue_registry.issues.items()):
        if (
            issue_domain != DOMAIN
            or not issue.data
            or issue.data.get("type") != "entity_renamed"
        ):
            continue
        if issue.data.get("new_entity_id") == old_entity_id:
            if issue.data.get("old_entity_id") == new_entity_id:
                # Renamed back: the stored reference works again.
                async_delete_issue(hass, DOMAIN, issue_id)
            else:
                placeholders = dict(issue.translation_placeholders or {})
                placeholders["new_entity_id"] = new_entity_id
                async_create_issue(
                    hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=issue.is_fixable or False,
                    is_persistent=True,
                    severity=IssueSeverity.ERROR,
                    translation_key=issue.translation_key or "entity_renamed",
                    translation_placeholders=placeholders,
                    data={**issue.data, "new_entity_id": new_entity_id},
                )
        elif issue.data.get("old_entity_id") == new_entity_id:
            async_delete_issue(hass, DOMAIN, issue_id)

    if DOMAIN not in hass.data:
        return
    for script_entity in hass.data[DOMAIN].entities:
        if old_entity_id not in script_entity.referenced_entities and (
            script_entity.raw_config is None
            or not entity_id_in_config(script_entity.raw_config, old_entity_id)
        ):
            continue
        if not isinstance(name := script_entity.name, str):
            name = script_entity.entity_id
        async_create_issue(
            hass,
            DOMAIN,
            f"{script_entity.entity_id}_entity_renamed_{old_entity_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.ERROR,
            translation_key="entity_renamed",
            translation_placeholders={
                "edit": f"/config/script/edit/{script_entity.unique_id}",
                "entity_id": script_entity.entity_id,
                "name": name,
                "old_entity_id": old_entity_id,
                "new_entity_id": new_entity_id,
            },
            data={
                "type": "entity_renamed",
                "config_id": script_entity.unique_id,
                "old_entity_id": old_entity_id,
                "new_entity_id": new_entity_id,
            },
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Load the scripts from the configuration."""
    hass.data[DOMAIN] = component = EntityComponent[BaseScriptEntity](
        LOGGER, DOMAIN, hass
    )

    # Register script as valid domain for Blueprint
    async_get_blueprints(hass)

    await async_process_config(hass, config, component)

    # Add some default blueprints to blueprints/script, does nothing
    # if blueprints/script already exists but still has to create
    # an executor job to check if the folder exists so we run it in a
    # separate task to avoid waiting for it to finish setting up
    # since a tracked task will be waited at the end of startup
    hass.async_create_task(
        async_get_blueprints(hass).async_populate(), eager_start=True
    )

    async_setup_services(hass)

    websocket_api.async_register_command(hass, websocket_config)

    hass.bus.async_listen(
        EVENT_ENTITY_REGISTRY_UPDATED,
        partial(_async_entity_renamed_issues, hass),
    )

    return True


@websocket_api.websocket_command({"type": "script/config", "entity_id": str})
@websocket_api.require_admin
def websocket_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get script config."""
    component: EntityComponent[BaseScriptEntity] = hass.data[DOMAIN]

    script = component.get_entity(msg["entity_id"])

    if script is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "config": script.raw_config,
        },
    )
