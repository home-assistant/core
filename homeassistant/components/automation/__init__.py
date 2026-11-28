"""Allow to set up simple automation rules via the config file."""

from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.const import (
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .config import async_validate_config_item
from .const import (
    ATTR_SOURCE,
    DATA_COMPONENT,
    DOMAIN,
    EVENT_AUTOMATION_RELOADED,
    EVENT_AUTOMATION_TRIGGERED,
    LOGGER,
    AutomationService,
)
from .dry_run import async_dry_run
from .entity import AutomationEntity, BaseAutomationEntity, UnavailableAutomationEntity
from .helpers import async_get_blueprints
from .services import async_setup_services
from .util import async_process_config, dry_run_input_from_config

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
    websocket_api.async_register_command(hass, websocket_dry_run)

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


@websocket_api.websocket_command(
    probatio.All(
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {
                probatio.Required("type"): "automation/dry_run",
                probatio.Optional("entity_id"): str,
                probatio.Optional("config"): dict,
            }
        ),
        probatio.ExactlyOne("entity_id", "config"),
    )
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_dry_run(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Evaluate an automation against the current state without running it."""
    if "config" in msg:
        try:
            config = await async_validate_config_item(hass, "", msg["config"])
        except (probatio.Invalid, HomeAssistantError) as err:
            connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
            return
        if TYPE_CHECKING:
            assert config is not None
        connection.send_result(
            msg["id"], await async_dry_run(hass, dry_run_input_from_config(config))
        )
        return

    automation = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])

    if automation is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    if not isinstance(automation, AutomationEntity):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_SUPPORTED,
            "Automation has an invalid configuration",
        )
        return

    connection.send_result(
        msg["id"],
        {
            "entity_id": automation.entity_id,
            **await async_dry_run(hass, automation.dry_run_input()),
        },
    )
