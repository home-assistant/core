"""Allow to set up simple automation rules via the config file."""

from functools import partial
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.const import (
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
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

from .const import (
    ATTR_SOURCE,
    DATA_COMPONENT,
    DOMAIN,
    EVENT_AUTOMATION_RELOADED,
    EVENT_AUTOMATION_TRIGGERED,
    LOGGER,
    AutomationService,
)
from .entity import AutomationEntity, BaseAutomationEntity, UnavailableAutomationEntity
from .helpers import async_get_blueprints
from .services import async_setup_services
from .util import async_process_config

ENTITY_ID_FORMAT = DOMAIN + ".{}"


ATTR_LAST_TRIGGERED = "last_triggered"

__all__ = [
    "ATTR_SOURCE",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "EVENT_AUTOMATION_RELOADED",
    "EVENT_AUTOMATION_TRIGGERED",
    "SERVICE_RELOAD",
    "SERVICE_TOGGLE",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "AutomationEntity",
    "AutomationService",
    "BaseAutomationEntity",
    "UnavailableAutomationEntity",
    "areas_in_automation",
    "automations_with_area",
    "automations_with_blueprint",
    "automations_with_device",
    "automations_with_entity",
    "automations_with_floor",
    "automations_with_label",
    "blueprint_in_automation",
    "devices_in_automation",
    "entities_in_automation",
    "floors_in_automation",
    "labels_in_automation",
]


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return true if specified automation entity_id is on.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


def _automations_with_x(
    hass: HomeAssistant, referenced_id: str, property_name: str
) -> list[str]:
    """Return all automations that reference the x."""
    if DATA_COMPONENT not in hass.data:
        return []

    return [
        automation_entity.entity_id
        for automation_entity in hass.data[DATA_COMPONENT].entities
        if referenced_id in getattr(automation_entity, property_name)
    ]


def _x_in_automation(
    hass: HomeAssistant, entity_id: str, property_name: str
) -> list[str]:
    """Return all x in an automation."""
    if DATA_COMPONENT not in hass.data:
        return []

    if (automation_entity := hass.data[DATA_COMPONENT].get_entity(entity_id)) is None:
        return []

    return list(getattr(automation_entity, property_name))


@callback
def automations_with_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all automations that reference the entity."""
    return _automations_with_x(hass, entity_id, "referenced_entities")


@callback
def entities_in_automation(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all entities in an automation."""
    return _x_in_automation(hass, entity_id, "referenced_entities")


@callback
def automations_with_device(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return all automations that reference the device."""
    return _automations_with_x(hass, device_id, "referenced_devices")


@callback
def devices_in_automation(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all devices in an automation."""
    return _x_in_automation(hass, entity_id, "referenced_devices")


@callback
def automations_with_area(hass: HomeAssistant, area_id: str) -> list[str]:
    """Return all automations that reference the area."""
    return _automations_with_x(hass, area_id, "referenced_areas")


@callback
def areas_in_automation(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all areas in an automation."""
    return _x_in_automation(hass, entity_id, "referenced_areas")


@callback
def automations_with_floor(hass: HomeAssistant, floor_id: str) -> list[str]:
    """Return all automations that reference the floor."""
    return _automations_with_x(hass, floor_id, "referenced_floors")


@callback
def floors_in_automation(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all floors in an automation."""
    return _x_in_automation(hass, entity_id, "referenced_floors")


@callback
def automations_with_label(hass: HomeAssistant, label_id: str) -> list[str]:
    """Return all automations that reference the label."""
    return _automations_with_x(hass, label_id, "referenced_labels")


@callback
def labels_in_automation(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all labels in an automation."""
    return _x_in_automation(hass, entity_id, "referenced_labels")


@callback
def automations_with_blueprint(hass: HomeAssistant, blueprint_path: str) -> list[str]:
    """Return all automations that reference the blueprint."""
    if DOMAIN not in hass.data:
        return []

    return [
        automation_entity.entity_id
        for automation_entity in hass.data[DATA_COMPONENT].entities
        if automation_entity.referenced_blueprint == blueprint_path
    ]


@callback
def blueprint_in_automation(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the blueprint the automation is based on or None."""
    if DATA_COMPONENT not in hass.data:
        return None

    if (automation_entity := hass.data[DATA_COMPONENT].get_entity(entity_id)) is None:
        return None

    return automation_entity.referenced_blueprint


@callback
def _async_entity_renamed_issues(
    hass: HomeAssistant, event: Event[EventEntityRegistryUpdatedData]
) -> None:
    """Create fixable issues for automations referencing a renamed entity."""
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

    if DATA_COMPONENT not in hass.data:
        return
    for automation_entity in hass.data[DATA_COMPONENT].entities:
        if old_entity_id not in automation_entity.referenced_entities and (
            automation_entity.raw_config is None
            or not entity_id_in_config(automation_entity.raw_config, old_entity_id)
        ):
            continue
        if not isinstance(name := automation_entity.name, str):
            name = automation_entity.entity_id
        if automation_entity.unique_id is None:
            async_create_issue(
                hass,
                DOMAIN,
                f"{automation_entity.entity_id}_entity_renamed_{old_entity_id}",
                is_fixable=False,
                is_persistent=True,
                severity=IssueSeverity.ERROR,
                translation_key="entity_renamed_yaml",
                translation_placeholders={
                    "entity_id": automation_entity.entity_id,
                    "name": name,
                    "old_entity_id": old_entity_id,
                    "new_entity_id": new_entity_id,
                },
                data={
                    "type": "entity_renamed",
                    "old_entity_id": old_entity_id,
                    "new_entity_id": new_entity_id,
                },
            )
            continue
        async_create_issue(
            hass,
            DOMAIN,
            f"{automation_entity.entity_id}_entity_renamed_{old_entity_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.ERROR,
            translation_key="entity_renamed",
            translation_placeholders={
                "edit": f"/config/automation/edit/{automation_entity.unique_id}",
                "entity_id": automation_entity.entity_id,
                "name": name,
                "old_entity_id": old_entity_id,
                "new_entity_id": new_entity_id,
            },
            data={
                "type": "entity_renamed",
                "config_id": automation_entity.unique_id,
                "old_entity_id": old_entity_id,
                "new_entity_id": new_entity_id,
            },
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up all automations."""
    hass.data[DATA_COMPONENT] = component = EntityComponent[BaseAutomationEntity](
        LOGGER, DOMAIN, hass
    )

    # Register automation as valid domain for Blueprint
    async_get_blueprints(hass)

    await async_process_config(hass, config, component)

    # Add some default blueprints to blueprints/automation, does nothing
    # if blueprints/automation already exists but still has to create
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


@websocket_api.websocket_command({"type": "automation/config", "entity_id": str})
@websocket_api.require_admin
def websocket_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get automation config."""
    automation = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])

    if automation is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "config": automation.raw_config,
        },
    )
