"""Repairs for ntfy integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_TOPIC


class TopicProtectedRepairFlow(RepairsFlow):
    """Handler for protected topic issue fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.entity_id = data["entity_id"]
        self.topic = data["topic"]

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Init repair flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Confirm repair flow."""
        if user_input is not None:
            er.async_get(self.hass).async_update_entity(
                self.entity_id,
                disabled_by=er.RegistryEntryDisabler.USER,
            )
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={CONF_TOPIC: self.topic},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str],
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("topic_protected"):
        return TopicProtectedRepairFlow(data)
    return ConfirmRepairFlow()
