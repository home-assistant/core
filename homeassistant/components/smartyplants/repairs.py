"""Repair issues for the SmartyPlants integration."""

import probatio

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .const import DOMAIN, LEGACY_FERTILISE_SUFFIX
from .coordinator import SmartyPlantsConfigEntry

LEGACY_ENTITIES_ISSUE = "legacy_entities"


@callback
def async_stranded_entity_ids(hass: HomeAssistant, entry_id: str) -> list[str]:
    """Return the entities the custom integration left that cannot be adopted.

    Adoption renames every entry it can, so whatever still carries the old
    suffix afterwards is an entry whose new unique id was already taken.
    """
    registry = er.async_get(hass)
    return sorted(
        registry_entry.entity_id
        for registry_entry in registry.entities.get_entries_for_config_entry_id(
            entry_id
        )
        if registry_entry.unique_id.endswith(LEGACY_FERTILISE_SUFFIX)
    )


@callback
def async_manage_legacy_entity_issue(
    hass: HomeAssistant, entry: SmartyPlantsConfigEntry
) -> None:
    """Raise or clear the issue for entities that could not be adopted."""
    issue_id = f"{LEGACY_ENTITIES_ISSUE}_{entry.entry_id}"

    if not (stranded := async_stranded_entity_ids(hass, entry.entry_id)):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=LEGACY_ENTITIES_ISSUE,
        translation_placeholders={
            "entities": "\n".join(f"- `{entity_id}`" for entity_id in stranded)
        },
        data={"entry_id": entry.entry_id},
        config_entry_id=entry.entry_id,
    )


class LegacyEntitiesRepairFlow(RepairsFlow):
    """Offer to delete the entities the custom integration left behind."""

    def __init__(self, entry_id: str) -> None:
        """Initialise the flow."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            registry = er.async_get(self.hass)
            # Read again rather than trusting the list the issue was raised
            # with, which the user may have worked through in the meantime.
            for entity_id in async_stranded_entity_ids(self.hass, self._entry_id):
                registry.async_remove(entity_id)
            return self.async_create_entry(data={})

        description_placeholders = None
        if issue := ir.async_get(self.hass).async_get_issue(
            self.handler, self.issue_id
        ):
            description_placeholders = issue.translation_placeholders

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders=description_placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for a SmartyPlants issue."""
    return LegacyEntitiesRepairFlow(str((data or {}).get("entry_id", "")))
