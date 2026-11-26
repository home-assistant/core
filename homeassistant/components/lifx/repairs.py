"""Repairs for LIFX."""

from typing import TYPE_CHECKING, override

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, INFRARED_BRIGHTNESS
from .coordinator import LIFXConfigEntry

DEPRECATED_INFRARED_SELECT = "deprecated_infrared_select"


def deprecated_infrared_select_issue_id(entry_id: str) -> str:
    """Return the repair issue ID for a device that still has the infrared select."""
    return f"{DEPRECATED_INFRARED_SELECT}_{entry_id}"


@callback
def _async_used_by(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return the automations and scripts that use an entity."""
    return automations_with_entity(hass, entity_id) + scripts_with_entity(
        hass, entity_id
    )


@callback
def async_deprecate_infrared_select(
    hass: HomeAssistant, entry: LIFXConfigEntry
) -> None:
    """Raise a repair issue for an infrared select, once automations have loaded."""
    coordinator = entry.runtime_data
    issue_id = deprecated_infrared_select_issue_id(entry.entry_id)

    @callback
    def _async_warn_or_remove(hass: HomeAssistant) -> None:
        """Warn about the select, or remove it once it is disabled and unused."""
        registry = er.async_get(hass)
        entity_id = coordinator.async_get_entity_id(
            Platform.SELECT, INFRARED_BRIGHTNESS
        )
        if entity_id is None or (select := registry.async_get(entity_id)) is None:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            return
        if select.disabled and not _async_used_by(hass, entity_id):
            registry.async_remove(entity_id)
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            return

        replacement_entity_id = coordinator.async_get_entity_id(
            Platform.NUMBER, INFRARED_BRIGHTNESS
        )
        if TYPE_CHECKING:
            assert replacement_entity_id is not None
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version="2027.7.0",
            config_entry_id=entry.entry_id,
            # The registry ID follows the select through a rename
            data={
                "select_id": select.id,
                "device_name": entry.title,
                "replacement_entity_id": replacement_entity_id,
            },
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=DEPRECATED_INFRARED_SELECT,
            translation_placeholders={"device_name": entry.title},
        )

    entry.async_on_unload(async_at_started(hass, _async_warn_or_remove))


@callback
def _async_format_used_by(registry: er.EntityRegistry, used_by: list[str]) -> str:
    """Format the automations and scripts using an entity as links to their editor."""
    return "\n".join(
        f"- [{item.name or item.original_name or used_by_entity_id}]"
        f"(/config/{item.domain}/edit/{item.unique_id})"
        if (item := registry.async_get(used_by_entity_id))
        else f"- `{used_by_entity_id}`"
        for used_by_entity_id in used_by
    )


class InvalidSerialRepairFlow(ConfirmRepairFlow):
    """Remove an entry whose serial cannot be migrated."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Remove the entry once the user confirms."""
        # The entry may have been deleted by hand while this flow was open
        if (
            user_input is not None
            and self.hass.config_entries.async_get_entry(self.entry_id) is not None
        ):
            await self.hass.config_entries.async_remove(self.entry_id)
        return await super().async_step_confirm(user_input)


class DeprecatedInfraredSelectRepairFlow(ConfirmRepairFlow):
    """Remove a deprecated infrared select once nothing uses it."""

    def __init__(
        self, select_id: str, device_name: str, replacement_entity_id: str
    ) -> None:
        """Store the select this flow removes and what replaces it."""
        self.select_id = select_id
        self.device_name = device_name
        self.replacement_entity_id = replacement_entity_id

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Remove the select once the user confirms."""
        registry = er.async_get(self.hass)
        if (select := registry.async_get(self.select_id)) is None:
            # Nothing can raise the issue again once the select is gone
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
            return self.async_abort(
                reason="already_removed",
                description_placeholders={"device_name": self.device_name},
            )

        placeholders = {
            "device_name": self.device_name,
            "entity_id": select.entity_id,
            "replacement_entity_id": self.replacement_entity_id,
        }
        if used_by := _async_used_by(self.hass, select.entity_id):
            return self.async_abort(
                reason="in_use",
                description_placeholders={
                    **placeholders,
                    "used_by": _async_format_used_by(registry, used_by),
                },
            )

        if user_input is None:
            return self.async_show_form(
                step_id="confirm", description_placeholders=placeholders
            )

        registry.async_remove(select.entity_id)
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for a LIFX repair issue."""
    assert data is not None
    if issue_id.startswith(f"{DEPRECATED_INFRARED_SELECT}_"):
        return DeprecatedInfraredSelectRepairFlow(
            str(data["select_id"]),
            str(data["device_name"]),
            str(data["replacement_entity_id"]),
        )
    return InvalidSerialRepairFlow(str(data["entry_id"]))
