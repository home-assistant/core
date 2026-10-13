"""Repairs for ntfy integration."""

import probatio

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_TOPIC, DOMAIN


class TopicProtectedRepairFlow(RepairsFlow):
    """Handler for protected topic issue fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.unique_id = data["unique_id"]
        self.topic = data["topic"]

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Init repair flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Confirm repair flow."""
        if user_input is not None:
            entity_registry = er.async_get(self.hass)
            # Resolved here since the entity_id may have changed
            if entity_id := entity_registry.async_get_entity_id(
                EVENT_DOMAIN, DOMAIN, self.unique_id
            ):
                entity_registry.async_update_entity(
                    entity_id,
                    disabled_by=er.RegistryEntryDisabler.USER,
                )
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
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
