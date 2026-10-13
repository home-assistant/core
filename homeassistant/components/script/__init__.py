"""Support for scripts."""

import asyncio
from dataclasses import dataclass
from typing import Any, cast

import probatio

from homeassistant.components import websocket_api
from homeassistant.const import (
    CONF_MODE,  # noqa: F401
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.async_ import create_eager_task

from .config import ScriptConfig, ValidationStatus
from .const import (
    ATTR_VARIABLES,
    DOMAIN,
    EVENT_SCRIPT_STARTED,  # noqa: F401
    LOGGER,
)
from .entity import BaseScriptEntity, ScriptEntity, UnavailableScriptEntity
from .helpers import async_get_blueprints

SCRIPT_TURN_ONOFF_SCHEMA = make_entity_service_schema(
    {probatio.Optional(ATTR_VARIABLES): {str: cv.match_all}}
)
RELOAD_SERVICE_SCHEMA = probatio.Schema({})


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Load the scripts from the configuration."""
    hass.data[DOMAIN] = component = EntityComponent[BaseScriptEntity](
        LOGGER, DOMAIN, hass
    )

    # Register script as valid domain for Blueprint
    async_get_blueprints(hass)

    await _async_process_config(hass, config, component)

    # Add some default blueprints to blueprints/script, does nothing
    # if blueprints/script already exists but still has to create
    # an executor job to check if the folder exists so we run it in a
    # separate task to avoid waiting for it to finish setting up
    # since a tracked task will be waited at the end of startup
    hass.async_create_task(
        async_get_blueprints(hass).async_populate(), eager_start=True
    )

    async def reload_service(service: ServiceCall) -> None:
        """Call a service to reload scripts."""
        await async_get_blueprints(hass).async_reset_cache()
        conf = await component.async_prepare_reload(skip_reset=True)
        await _async_process_config(hass, conf, component)

    async def turn_on_service(service: ServiceCall) -> None:
        """Call a service to turn script on."""
        variables = service.data.get(ATTR_VARIABLES)
        script_entities = await component.async_extract_from_service(service)
        for script_entity in script_entities:
            await script_entity.async_turn_on(
                variables=variables, context=service.context, wait=False
            )

    async def turn_off_service(service: ServiceCall) -> None:
        """Cancel a script."""
        # Stopping a script is ok to be done in parallel
        script_entities = await component.async_extract_from_service(service)

        if not script_entities:
            return

        for script_entity in script_entities:
            script_entity.async_set_context(service.context)

        await asyncio.wait(
            [
                create_eager_task(script_entity.async_turn_off())
                for script_entity in script_entities
            ]
        )

    async def toggle_service(service: ServiceCall) -> None:
        """Toggle a script."""
        script_entities = await component.async_extract_from_service(service)
        for script_entity in script_entities:
            await script_entity.async_toggle(context=service.context, wait=False)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service, schema=RELOAD_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, turn_on_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, turn_off_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, toggle_service, schema=SCRIPT_TURN_ONOFF_SCHEMA
    )

    websocket_api.async_register_command(hass, websocket_config)

    return True


@dataclass(slots=True)
class ScriptEntityConfig:
    """Container for prepared script entity configuration."""

    config_block: ConfigType
    key: str
    raw_blueprint_inputs: ConfigType | None
    raw_config: ConfigType | None
    validation_error: str | None
    validation_status: ValidationStatus


async def _prepare_script_config(
    hass: HomeAssistant,
    config: ConfigType,
) -> list[ScriptEntityConfig]:
    """Parse configuration and prepare script entity configuration."""
    script_configs: list[ScriptEntityConfig] = []

    conf: dict[str, ConfigType] = config[DOMAIN]

    for key, config_block in conf.items():
        raw_config = cast(ScriptConfig, config_block).raw_config
        raw_blueprint_inputs = cast(ScriptConfig, config_block).raw_blueprint_inputs
        validation_error = cast(ScriptConfig, config_block).validation_error
        validation_status = cast(ScriptConfig, config_block).validation_status

        script_configs.append(
            ScriptEntityConfig(
                config_block,
                key,
                raw_blueprint_inputs,
                raw_config,
                validation_error,
                validation_status,
            )
        )

    return script_configs


async def _create_script_entities(
    hass: HomeAssistant, script_configs: list[ScriptEntityConfig]
) -> list[BaseScriptEntity]:
    """Create script entities from prepared configuration."""
    entities: list[BaseScriptEntity] = []

    for script_config in script_configs:
        if script_config.validation_status != ValidationStatus.OK:
            entities.append(
                UnavailableScriptEntity(
                    script_config.key,
                    script_config.raw_config,
                    script_config.raw_blueprint_inputs,
                    cast(str, script_config.validation_error),
                    script_config.validation_status,
                )
            )
            continue

        entity = ScriptEntity(
            hass,
            script_config.key,
            script_config.config_block,
            script_config.raw_config,
            script_config.raw_blueprint_inputs,
        )
        entities.append(entity)

    return entities


async def _async_process_config(
    hass: HomeAssistant,
    config: ConfigType,
    component: EntityComponent[BaseScriptEntity],
) -> None:
    """Process script configuration."""
    entities = []

    def script_matches_config(
        script: BaseScriptEntity, config: ScriptEntityConfig
    ) -> bool:
        return script.unique_id == config.key and script.raw_config == config.raw_config

    def find_matches(
        scripts: list[BaseScriptEntity],
        script_configs: list[ScriptEntityConfig],
    ) -> tuple[set[int], set[int]]:
        """Find matches between a list of script entities and a list of configurations.

        A script or configuration is only allowed to match at most once to handle
        the case of multiple scripts with identical configuration.

        Returns a tuple of sets of indices: ({script_matches}, {config_matches})
        """
        script_matches: set[int] = set()
        config_matches: set[int] = set()

        for script_idx, script in enumerate(scripts):
            for config_idx, script_config in enumerate(script_configs):
                if config_idx in config_matches:
                    # Only allow a script config to match at most once
                    continue
                if script_matches_config(script, script_config):
                    script_matches.add(script_idx)
                    config_matches.add(config_idx)
                    # Only allow a script to match at most once
                    break

        return script_matches, config_matches

    script_configs = await _prepare_script_config(hass, config)
    scripts: list[BaseScriptEntity] = list(component.entities)

    # Find scripts and configurations which have matches
    script_matches, config_matches = find_matches(scripts, script_configs)

    # Remove scripts which have changed config or no longer exist
    tasks = [
        script.async_remove()
        for idx, script in enumerate(scripts)
        if idx not in script_matches
    ]
    await asyncio.gather(*tasks)

    # Create scripts which have changed config or have been added
    updated_script_configs = [
        config for idx, config in enumerate(script_configs) if idx not in config_matches
    ]
    entities = await _create_script_entities(hass, updated_script_configs)
    await component.async_add_entities(entities)


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
