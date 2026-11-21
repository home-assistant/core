"""Repairs for automations."""

from typing import Any

import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config import AUTOMATION_CONFIG_PATH
from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.script import replace_entity_id_in_config
from homeassistant.util.file import write_utf8_file_atomic
from homeassistant.util.yaml import dump, load_yaml

from .const import DOMAIN


async def _async_update_entity_references(
    hass: HomeAssistant, config_id: str, old_entity_id: str, new_entity_id: str
) -> bool:
    """Update references to a renamed entity in the stored config."""
    path = hass.config.path(AUTOMATION_CONFIG_PATH)

    def _update() -> bool:
        try:
            items = load_yaml(path)
        except FileNotFoundError:
            return False
        if not isinstance(items, list):
            return False
        for index, item in enumerate(items):
            if item.get(CONF_ID) != config_id:
                continue
            new_item, changed = replace_entity_id_in_config(
                item, old_entity_id, new_entity_id
            )
            if not changed:
                return False
            items[index] = new_item
            write_utf8_file_atomic(path, dump(items))
            return True
        return False

    if not await hass.async_add_executor_job(_update):
        return False
    await hass.services.async_call(
        DOMAIN, SERVICE_RELOAD, {CONF_ID: config_id}, blocking=True
    )
    return True


class EntityRenamedFlow(RepairsFlow):
    """Update the references in the automation to a renamed entity."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize the flow."""
        self._data = data

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        issue = ir.async_get(self.hass).async_get_issue(self.handler, self.issue_id)
        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders=(
                issue.translation_placeholders if issue is not None else None
            ),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if not await _async_update_entity_references(
            self.hass,
            self._data["config_id"],
            self._data["old_entity_id"],
            self._data["new_entity_id"],
        ):
            return self.async_abort(reason="cannot_update")
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if data is not None and data.get("type") == "entity_renamed":
        return EntityRenamedFlow(data)
    return ConfirmRepairFlow()
