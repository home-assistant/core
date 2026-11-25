"""Utilities for the script integration."""

import asyncio
from dataclasses import dataclass
from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.issue_registry import async_refresh_issues
from homeassistant.helpers.typing import ConfigType

from .config import ScriptConfig, ValidationStatus
from .const import DOMAIN
from .entity import BaseScriptEntity, ScriptEntity, UnavailableScriptEntity


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


async def async_process_config(
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

    removed_scripts = [
        script for idx, script in enumerate(scripts) if idx not in script_matches
    ]
    # Repair issues of removed scripts are kept if the new scripts re-create them,
    # which preserves the user's ignore flag
    broken_scripts = [
        script
        for script in removed_scripts
        if isinstance(script, UnavailableScriptEntity)
    ]
    with async_refresh_issues(
        hass, DOMAIN, issue_ids=[script.repair_issue_id for script in broken_scripts]
    ):
        # Remove scripts which have changed config or no longer exist
        await asyncio.gather(*(script.async_remove() for script in removed_scripts))

        # Create scripts which have changed config or have been added
        updated_script_configs = [
            config
            for idx, config in enumerate(script_configs)
            if idx not in config_matches
        ]
        entities = await _create_script_entities(hass, updated_script_configs)
        await component.async_add_entities(entities)
