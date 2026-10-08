"""Allow to set up simple automation rules via the config file."""

import asyncio
from dataclasses import dataclass
from typing import Any, cast

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition as condition_helper
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
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.service import (
    ReloadServiceHelper,
    async_register_admin_service,
)
from homeassistant.helpers.typing import ConfigType

from .config import AutomationConfig, ValidationStatus
from .const import (  # noqa: F401
    ATTR_SOURCE,
    CONF_INITIAL_STATE,
    CONF_TRACE,
    CONF_TRIGGER_VARIABLES,
    DATA_COMPONENT,
    DOMAIN,
    EVENT_AUTOMATION_TRIGGERED,
    LOGGER,
)
from .entity import (
    AutomationEntity,
    BaseAutomationEntity,
    IfAction,
    UnavailableAutomationEntity,
)
from .helpers import async_get_blueprints
from .services import async_setup_services

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

    await _async_process_config(hass, config, component)

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
            await _async_process_single_config(hass, conf, component, automation_id)
        else:
            await _async_process_config(hass, conf, component)
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


@dataclass(slots=True)
class AutomationEntityConfig:
    """Container for prepared automation entity configuration."""

    config_block: ConfigType
    list_no: int
    raw_blueprint_inputs: ConfigType | None
    raw_config: ConfigType | None
    validation_error: str | None
    validation_status: ValidationStatus


async def _prepare_automation_config(
    hass: HomeAssistant,
    config: ConfigType,
    wanted_automation_id: str | None,
) -> list[AutomationEntityConfig]:
    """Parse configuration and prepare automation entity configuration."""
    automation_configs: list[AutomationEntityConfig] = []

    conf: list[ConfigType] = config[DOMAIN]

    for list_no, config_block in enumerate(conf):
        automation_id: str | None = config_block.get(CONF_ID)
        if wanted_automation_id is not None and automation_id != wanted_automation_id:
            continue

        raw_config = cast(AutomationConfig, config_block).raw_config
        raw_blueprint_inputs = cast(AutomationConfig, config_block).raw_blueprint_inputs
        validation_error = cast(AutomationConfig, config_block).validation_error
        validation_status = cast(AutomationConfig, config_block).validation_status
        automation_configs.append(
            AutomationEntityConfig(
                config_block,
                list_no,
                raw_blueprint_inputs,
                raw_config,
                validation_error,
                validation_status,
            )
        )

    return automation_configs


def _automation_name(automation_config: AutomationEntityConfig) -> str:
    """Return the configured name of an automation."""
    config_block = automation_config.config_block
    list_no = automation_config.list_no
    return config_block.get(CONF_ALIAS) or f"{DOMAIN} {list_no}"


async def _create_automation_entities(
    hass: HomeAssistant, automation_configs: list[AutomationEntityConfig]
) -> list[BaseAutomationEntity]:
    """Create automation entities from prepared configuration."""
    entities: list[BaseAutomationEntity] = []

    for automation_config in automation_configs:
        config_block = automation_config.config_block

        automation_id: str | None = config_block.get(CONF_ID)
        name = _automation_name(automation_config)

        if automation_config.validation_status != ValidationStatus.OK:
            entities.append(
                UnavailableAutomationEntity(
                    automation_id,
                    name,
                    automation_config.raw_config,
                    automation_config.raw_blueprint_inputs,
                    cast(str, automation_config.validation_error),
                    automation_config.validation_status,
                )
            )
            continue

        initial_state: bool | None = config_block.get(CONF_INITIAL_STATE)

        action_script = Script(
            hass,
            config_block[CONF_ACTIONS],
            name,
            DOMAIN,
            running_description="automation actions",
            script_mode=config_block[CONF_MODE],
            max_runs=config_block[CONF_MAX],
            max_exceeded=config_block[CONF_MAX_EXCEEDED],
            logger=LOGGER,
            # We don't pass variables here
            # Automation will already render them to use them in the condition
            # and so will pass them on to the script.
        )

        if CONF_CONDITIONS in config_block:
            condition = await _async_process_if(hass, name, config_block)

            if condition is None:
                continue
        else:
            condition = None

        # Add trigger variables to variables
        variables = None
        if CONF_TRIGGER_VARIABLES in config_block and CONF_VARIABLES in config_block:
            variables = ScriptVariables(
                dict(config_block[CONF_TRIGGER_VARIABLES].as_dict())
            )
            variables.variables.update(config_block[CONF_VARIABLES].as_dict())
        elif CONF_TRIGGER_VARIABLES in config_block:
            variables = config_block[CONF_TRIGGER_VARIABLES]
        elif CONF_VARIABLES in config_block:
            variables = config_block[CONF_VARIABLES]

        entity = AutomationEntity(
            automation_id,
            name,
            config_block[CONF_TRIGGERS],
            condition,
            action_script,
            initial_state,
            variables,
            config_block.get(CONF_TRIGGER_VARIABLES),
            automation_config.raw_config,
            automation_config.raw_blueprint_inputs,
            config_block[CONF_TRACE],
        )
        entities.append(entity)

    return entities


async def _async_process_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    component: EntityComponent[BaseAutomationEntity],
) -> None:
    """Process config and add automations."""

    def automation_matches_config(
        automation: BaseAutomationEntity, config: AutomationEntityConfig
    ) -> bool:
        name = _automation_name(config)
        return automation.name == name and automation.raw_config == config.raw_config

    def find_matches(
        automations: list[BaseAutomationEntity],
        automation_configs: list[AutomationEntityConfig],
    ) -> tuple[set[int], set[int]]:
        """Find matches between automation entities and configurations.

        An automation or configuration is only allowed to match at most once to handle
        the case of multiple automations with identical configuration.

        Returns a tuple of sets of indices: ({automation_matches}, {config_matches})
        """
        automation_matches: set[int] = set()
        config_matches: set[int] = set()
        automation_configs_with_id: dict[str, tuple[int, AutomationEntityConfig]] = {}
        automation_configs_without_id: list[tuple[int, AutomationEntityConfig]] = []

        for config_idx, automation_config in enumerate(automation_configs):
            if automation_id := automation_config.config_block.get(CONF_ID):
                automation_configs_with_id[automation_id] = (
                    config_idx,
                    automation_config,
                )
                continue
            automation_configs_without_id.append((config_idx, automation_config))

        for automation_idx, automation in enumerate(automations):
            if automation.unique_id:
                if automation.unique_id not in automation_configs_with_id:
                    continue
                config_idx, automation_config = automation_configs_with_id.pop(
                    automation.unique_id
                )
                if automation_matches_config(automation, automation_config):
                    automation_matches.add(automation_idx)
                    config_matches.add(config_idx)
                continue

            for config_idx, automation_config in automation_configs_without_id:
                if config_idx in config_matches:
                    # Only allow an automation config to match at most once
                    continue
                if automation_matches_config(automation, automation_config):
                    automation_matches.add(automation_idx)
                    config_matches.add(config_idx)
                    # Only allow an automation to match at most once
                    break

        return automation_matches, config_matches

    automation_configs = await _prepare_automation_config(hass, config, None)
    automations: list[BaseAutomationEntity] = list(component.entities)

    # Find automations and configurations which have matches
    automation_matches, config_matches = find_matches(automations, automation_configs)

    # Remove automations which have changed config or no longer exist
    tasks = [
        automation.async_remove()
        for idx, automation in enumerate(automations)
        if idx not in automation_matches
    ]
    await asyncio.gather(*tasks)

    # Create automations which have changed config or have been added
    updated_automation_configs = [
        config
        for idx, config in enumerate(automation_configs)
        if idx not in config_matches
    ]
    entities = await _create_automation_entities(hass, updated_automation_configs)
    await component.async_add_entities(entities)


def _automation_matches_config(
    automation: BaseAutomationEntity | None, config: AutomationEntityConfig | None
) -> bool:
    """Return False if an automation's config has been changed."""
    if not automation:
        return False
    if not config:
        return False
    name = _automation_name(config)
    return automation.name == name and automation.raw_config == config.raw_config


async def _async_process_single_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    component: EntityComponent[BaseAutomationEntity],
    automation_id: str,
) -> None:
    """Process config and add a single automation."""

    automation_configs = await _prepare_automation_config(hass, config, automation_id)
    automation = next(
        (x for x in component.entities if x.unique_id == automation_id), None
    )
    automation_config = automation_configs[0] if automation_configs else None

    if _automation_matches_config(automation, automation_config):
        return

    if automation:
        await automation.async_remove()
    entities = await _create_automation_entities(hass, automation_configs)
    await component.async_add_entities(entities)


async def _async_process_if(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> IfAction | None:
    """Process if checks."""
    if_configs = config[CONF_CONDITIONS]

    try:
        if_action = await condition_helper.async_conditions_from_config(
            hass, if_configs, LOGGER, name
        )
    except HomeAssistantError as ex:
        LOGGER.warning("Invalid condition: %s", ex)
        return None

    result: IfAction = if_action  # type: ignore[assignment]
    result.config = if_configs

    return result


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
