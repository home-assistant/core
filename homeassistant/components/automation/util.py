"""Config processing for the automation integration."""

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.const import (
    CONF_ACTIONS,
    CONF_ALIAS,
    CONF_CONDITIONS,
    CONF_ID,
    CONF_MODE,
    CONF_TRIGGERS,
    CONF_VARIABLES,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition as condition_helper
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.script import CONF_MAX, CONF_MAX_EXCEEDED, Script
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.typing import ConfigType

from .config import AutomationConfig, ValidationStatus
from .const import (
    CONF_INITIAL_STATE,
    CONF_TRACE,
    CONF_TRIGGER_VARIABLES,
    DOMAIN,
    LOGGER,
)
from .entity import (
    AutomationEntity,
    BaseAutomationEntity,
    IfAction,
    UnavailableAutomationEntity,
)


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


async def async_process_config(
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


async def async_process_single_config(
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
