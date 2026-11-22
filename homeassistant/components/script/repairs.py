"""Repairs for scripts."""

from pathlib import Path
import re
from typing import Any

import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config import SCRIPT_CONFIG_PATH
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.script import (
    entity_id_in_config,
    replace_entity_id_in_config,
)
from homeassistant.util.file import file_lock, write_utf8_file_atomic
from homeassistant.util.yaml import dump, load_yaml

from .const import DOMAIN

# YAML directives like !include or !env_var must not be expanded into the file.
_YAML_DIRECTIVE = re.compile(r"!(include|env_var|secret)\b")


def _update_entity_references(
    path: str, config_id: str, old_entity_id: str, new_entity_id: str
) -> bool:
    """Replace references to a renamed entity in the stored config."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return False
    if _YAML_DIRECTIVE.search(raw):
        return False
    try:
        items = load_yaml(path)
    except HomeAssistantError, OSError:
        return False
    if not isinstance(items, dict) or config_id not in items:
        return False
    new_item, changed = replace_entity_id_in_config(
        items[config_id], old_entity_id, new_entity_id
    )
    if not changed:
        return False
    items[config_id] = new_item
    try:
        write_utf8_file_atomic(path, dump(items), private=True)
    except OSError:
        return False
    return True


async def _async_update_entity_references(
    hass: HomeAssistant, config_id: str, old_entity_id: str, new_entity_id: str
) -> str:
    """Update references to a renamed entity in the stored config."""
    path = hass.config.path(SCRIPT_CONFIG_PATH)

    async with file_lock(path):
        if not await hass.async_add_executor_job(
            _update_entity_references, path, config_id, old_entity_id, new_entity_id
        ):
            return "cannot_update"
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    script_entity = next(
        (
            entity
            for entity in hass.data[DOMAIN].entities
            if entity.unique_id == config_id
        ),
        None,
    )
    if script_entity is not None and (
        old_entity_id in script_entity.referenced_entities
        or (
            script_entity.raw_config is not None
            and entity_id_in_config(script_entity.raw_config, old_entity_id)
        )
    ):
        # Other references remain, e.g. inside blueprint actions.
        return "still_referenced"
    return "updated"


class EntityRenamedFlow(RepairsFlow):
    """Update the references in the script to a renamed entity."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize the flow."""
        self._data = data

    def _issue_placeholders(self) -> dict[str, str] | None:
        """Return the issue's translation placeholders."""
        issue = ir.async_get(self.hass).async_get_issue(self.handler, self.issue_id)
        return issue.translation_placeholders if issue is not None else None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders=self._issue_placeholders(),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is None:
            return await self.async_step_init()
        match await _async_update_entity_references(
            self.hass,
            self._data["config_id"],
            self._data["old_entity_id"],
            self._data["new_entity_id"],
        ):
            case "updated":
                return self.async_create_entry(data={})
            case reason:
                return self.async_abort(
                    reason=reason,
                    description_placeholders=self._issue_placeholders(),
                )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if data is not None and data.get("type") == "entity_renamed":
        return EntityRenamedFlow(data)
    return ConfirmRepairFlow()
