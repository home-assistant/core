"""Repair flows for the LIFX integration."""

from typing import cast

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import async_delete_issue

from .const import DOMAIN


@callback
def _async_format_used_by(
    registry: er.EntityRegistry, automations: list[str], scripts: list[str]
) -> str:
    """Format the automations and scripts using an entity as links to their editor."""
    return "\n".join(
        f"- [{item.name or item.original_name or used_by_entity_id}]"
        f"(/config/{integration}/edit/{item.unique_id})"
        if (item := registry.async_get(used_by_entity_id))
        else f"- `{used_by_entity_id}`"
        for integration, entity_ids in (
            ("automation", automations),
            ("script", scripts),
        )
        for used_by_entity_id in entity_ids
    )


class DeprecatedInfraredSelectRepairFlow(RepairsFlow):
    """Handler for removing a deprecated infrared brightness select entity."""

    def __init__(
        self, entity_id: str, entity_name: str, replacement_entity_id: str
    ) -> None:
        """Store the select entity this flow removes and what supersedes it."""
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.replacement_entity_id = replacement_entity_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Remove the select entity after receiving confirmation."""
        placeholders = {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "replacement_entity_id": self.replacement_entity_id,
        }
        registry = er.async_get(self.hass)
        if registry.async_get(self.entity_id) is None:
            # An abort leaves the issue in place, but nothing can recreate it
            # once the entity it is about has been removed by hand
            async_delete_issue(self.hass, DOMAIN, self.issue_id)
            return self.async_abort(
                reason="already_removed", description_placeholders=placeholders
            )

        automations = automations_with_entity(self.hass, self.entity_id)
        scripts = scripts_with_entity(self.hass, self.entity_id)
        if automations or scripts:
            return self.async_abort(
                reason="in_use",
                description_placeholders={
                    **placeholders,
                    "used_by": _async_format_used_by(registry, automations, scripts),
                },
            )

        if user_input is None:
            return self.async_show_form(
                step_id="confirm", description_placeholders=placeholders
            )

        registry.async_remove(self.entity_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow that fixes an issue."""
    assert data is not None
    return DeprecatedInfraredSelectRepairFlow(
        cast(str, data["entity_id"]),
        cast(str, data["entity_name"]),
        cast(str, data["replacement_entity_id"]),
    )
