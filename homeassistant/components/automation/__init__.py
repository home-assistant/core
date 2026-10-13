"""Allow to set up simple automation rules via the config file."""

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.const import (  # noqa: F401
    ATTR_AREA_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    ATTR_MODE,
    ATTR_NAME,
    CONF_ACTIONS,
    CONF_ALIAS,
    CONF_CONDITIONS,
    CONF_ID,
    CONF_MODE,
    CONF_PATH,
    CONF_TRIGGERS,
    CONF_VARIABLES,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.script import (  # noqa: F401
    ATTR_CUR,
    ATTR_MAX,
    CONF_MAX,
    CONF_MAX_EXCEEDED,
    Script,
    ScriptRunResult,
    script_stack_cv,
)
from homeassistant.helpers.service import (
    ReloadServiceHelper,
    async_register_admin_service,
)
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_SOURCE,
    DATA_COMPONENT,
    DOMAIN,
    EVENT_AUTOMATION_TRIGGERED,
    LOGGER,
)
from .entity import (  # noqa: F401
    AutomationEntity,
    BaseAutomationEntity,
    UnavailableAutomationEntity,
)
from .helpers import async_get_blueprints
from .services import async_setup_services
from .util import async_process_config, async_process_single_config

ENTITY_ID_FORMAT = DOMAIN + ".{}"

EVENT_AUTOMATION_RELOADED = "automation_reloaded"

ATTR_LAST_TRIGGERED = "last_triggered"


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

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Remove all automations and load new ones from config."""
        await async_get_blueprints(hass).async_reset_cache()
        conf = await component.async_prepare_reload(skip_reset=True)
        if automation_id := service_call.data.get(CONF_ID):
            await async_process_single_config(hass, conf, component, automation_id)
        else:
            await async_process_config(hass, conf, component)
        hass.bus.async_fire(EVENT_AUTOMATION_RELOADED, context=service_call.context)

    def reload_targets(service_call: ServiceCall) -> set[str | None]:
        if automation_id := service_call.data.get(CONF_ID):
            return {automation_id}
        return {automation.unique_id for automation in component.entities}

    reload_helper = ReloadServiceHelper(reload_service_handler, reload_targets)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_helper.execute_service,
        schema=probatio.Schema({probatio.Optional(CONF_ID): str}),
    )

    websocket_api.async_register_command(hass, websocket_config)

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
